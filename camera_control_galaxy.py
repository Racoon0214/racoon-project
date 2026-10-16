# -*- coding: utf-8 -*-
"""
大恒 Galaxy 工业相机接入模块（高清广角版）。

【定位】
与 camera_control_usb.py 完全同接口（类名、方法签名、属性名一致），
是它的"即插即用"替代件。将来新相机到了，只需把 cameraV4.py 里的：
    from camera_control_usb import Camera
改成：
    from camera_control_galaxy import Camera
其余代码一行都不用动。

【接口契约（cameraV4.py 依赖的）】
    Camera(device_index=0, username=None, password=None)   构造
    .open_camera()                                         打开相机（或 999=视频文件）
    .get_frame() -> numpy BGR 数组(H,W,3) 或 None          取一帧（BGR！cv2/YOLO 需要）
    .close_camera()                                        关闭
    .LoginDev()                                            登录校验（照搬 usb 版）
    .list_connected_cameras() -> [0-based index,...]       枚举相机
    属性：width, height, is_opened, device_index, available_cameras_index, video_path

【关键注意】
1. 大恒 Galaxy Python SDK 叫 gxipy，相机到了必须先装 Galaxy SDK（含 USB 驱动 +
   GenTL 注册），否则 gxipy 导入失败。未装时本模块不会崩溃，仅 device_index!=999
   的真实相机分支不可用；device_index==999 的视频文件回退模式仍可离线联调。
2. gxipy 枚举相机是 1-based（open_device_by_index(1)=第1台），本模块对外仍用
   0-based：内部已做 device_index+1 映射。
3. 大恒彩色相机默认输出 Bayer，必须经 ImageFormatConvert 转成 RGB；而 cv2/YOLO
   需要 BGR —— get_frame 里已强制 RGB->BGR 翻转。漏掉这步颜色会反、属性识别
   颜色全错。
4. 默认关闭自动曝光/增益/白平衡（固定安装工业相机求稳定、不闪烁、颜色一致），
   均集中在文件顶部常量，可随时翻成自动。
"""

import os
import sys
import time
import cv2

# ====== 大恒 Galaxy Python SDK (gxipy) 导入（延迟容错） ======
# 相机未到 / 未装 SDK 时，仅 video 文件模式(999)可用；真正打开相机会用到。
# 若首次 import 失败，自动把 SDK 的 Python Samples 目录加入搜索路径再试一次；
# 仍失败则置 _GX_AVAILABLE=False，open_camera 时给出明确指引。
GX_SAMPLES_DIR = r"D:/01AIWorkSpace/BearVision/后羿专用视觉/大恒图像资料/Development/Samples/Python"
_GX_AVAILABLE = False
gx = None
try:
    import gxipy as gx
    from gxipy.gxidef import *  # GxPixelFormatEntry / GxFrameStatusList / DxValidBit 等
    _GX_AVAILABLE = True
except ImportError:
    if GX_SAMPLES_DIR and os.path.isdir(GX_SAMPLES_DIR) and GX_SAMPLES_DIR not in sys.path:
        sys.path.insert(0, GX_SAMPLES_DIR)
        try:
            import gxipy as gx
            from gxipy.gxidef import *
            _GX_AVAILABLE = True
        except ImportError:
            pass

from ctypes import c_ubyte, addressof
import numpy


# ====== 大恒相机参数（固定安装工业相机，关自动以求稳定） ======
# 光照固定后这些固定值比自动更稳：既消除"框闪烁"的相机层来源，也让属性颜色一致。
#
# 【核心语义：调大 = 画面更亮 = 用于"暗光/光线不足"场景；调小 = 画面更暗 = 用于"强光/过曝"场景】
#   - 现场只有"室外正午全日光"约 50% 的强度（进光减半）→ 需要把画面整体提亮来补偿。
#   - 优先用【曝光时间】提亮：进光量随曝光时间线性增加，且无噪声代价（仅长曝光可能引入运动模糊）。
#   - 【增益】是"不得已才加"的提亮手段：提亮同时放大传感器噪声，伤害检测框稳定性与属性识别，
#     因此尽量压低，只在"曝光已拉满仍偏暗"或"需短曝光抓快动作"时才上调。
#
# 曝光时间（微秒）：每多 1µs 曝光，进光量线性增加 → 画面变亮。
GALAXY_EXPOSURE_TIME_US = 40000.0   # 曝光 40ms。范围常见 10µs ~ 1s(1000000µs)，机型上限见规格书。
                                  # 本次默认：原 20ms 翻倍到 40ms，正好补回"只有 50% 日光"损失的亮度。
                                  # 调大→更亮(暗光/逆光用)；调小→更暗(防过曝)。注意：超过帧周期会降低帧率并增加运动模糊。
# 增益（dB）：放大传感器信号 → 画面变亮，但同步放大噪声。
GALAXY_GAIN_DB = 13.0              # 增益 13dB。范围常见 0 ~ 24dB(机型不同上限不同)。
                                  # 本次默认：保持 13(低噪声)。只有在"曝光已拉满仍偏暗"或"需要短曝光抓快动作"时才上调，每 +3dB≈亮度×1.4。
                                  # 调大→更亮但噪点多(暗光补光用)；调小→画面更干净但偏暗。
GALAXY_AUTO_EXPOSURE = False       # False=固定曝光(稳定不闪)；True=相机自动(会随光微变→闪烁+属性色漂)
GALAXY_AUTO_GAIN = False           # False=固定增益
GALAXY_AUTO_WHITE_BALANCE = False  # False=固定白平衡(属性颜色一致)；True=自动(开箱即色但会漂移)


def _get_best_valid_bits(pixel_format):
    """从大恒示例搬来的有效位判定（不同像素格式位深不同，转 RGB 必须用对）。"""
    valid_bits = DxValidBit.BIT0_7
    if pixel_format in (GxPixelFormatEntry.MONO8,
                        GxPixelFormatEntry.BAYER_GR8, GxPixelFormatEntry.BAYER_RG8,
                        GxPixelFormatEntry.BAYER_GB8, GxPixelFormatEntry.BAYER_BG8,
                        GxPixelFormatEntry.RGB8, GxPixelFormatEntry.BGR8,
                        GxPixelFormatEntry.R8, GxPixelFormatEntry.G8, GxPixelFormatEntry.B8):
        valid_bits = DxValidBit.BIT0_7
    elif pixel_format in (GxPixelFormatEntry.MONO10, GxPixelFormatEntry.MONO10_PACKED, GxPixelFormatEntry.MONO10_P,
                          GxPixelFormatEntry.BAYER_GR10, GxPixelFormatEntry.BAYER_RG10,
                          GxPixelFormatEntry.BAYER_GB10, GxPixelFormatEntry.BAYER_BG10,
                          GxPixelFormatEntry.BAYER_GR10_P, GxPixelFormatEntry.BAYER_RG10_P,
                          GxPixelFormatEntry.BAYER_GB10_P, GxPixelFormatEntry.BAYER_GR10_PACKED,
                          GxPixelFormatEntry.BAYER_RG10_PACKED, GxPixelFormatEntry.BAYER_GB10_PACKED):
        valid_bits = DxValidBit.BIT2_9
    elif pixel_format in (GxPixelFormatEntry.MONO12, GxPixelFormatEntry.MONO12_PACKED, GxPixelFormatEntry.MONO12_P,
                          GxPixelFormatEntry.BAYER_GR12, GxPixelFormatEntry.BAYER_RG12,
                          GxPixelFormatEntry.BAYER_GB12, GxPixelFormatEntry.BAYER_BG12,
                          GxPixelFormatEntry.BAYER_GR12_P, GxPixelFormatEntry.BAYER_RG12_P,
                          GxPixelFormatEntry.BAYER_GB12_P, GxPixelFormatEntry.BAYER_BG12_P,
                          GxPixelFormatEntry.BAYER_GR12_PACKED, GxPixelFormatEntry.BAYER_RG12_PACKED,
                          GxPixelFormatEntry.BAYER_GB12_PACKED):
        valid_bits = DxValidBit.BIT4_11
    elif pixel_format in (GxPixelFormatEntry.MONO14, GxPixelFormatEntry.MONO14_P,
                          GxPixelFormatEntry.BAYER_GR14, GxPixelFormatEntry.BAYER_RG14,
                          GxPixelFormatEntry.BAYER_GB14, GxPixelFormatEntry.BAYER_RG14_P,
                          GxPixelFormatEntry.BAYER_GB14_P):
        valid_bits = DxValidBit.BIT6_13
    elif pixel_format in (GxPixelFormatEntry.MONO16,
                          GxPixelFormatEntry.BAYER_GR16, GxPixelFormatEntry.BAYER_RG16,
                          GxPixelFormatEntry.BAYER_GB16, GxPixelFormatEntry.BAYER_BG16):
        valid_bits = DxValidBit.BIT8_15
    return valid_bits


class Camera:
    def __init__(self, device_index=0, username=None, password=None):
        # 与 usb 版保持一致的属性，方便 cameraV4.py 无缝替换
        self.username = username
        self.password = password

        self.device_index = int(device_index)
        self.width = 1920          # 默认值；打开相机后会被真实帧尺寸覆盖
        self.height = 1080
        self.capture = None        # 视频文件模式(cv2)句柄；真实相机模式不使用
        self.is_opened = False
        self.available_cameras_index = None

        # 大恒 Galaxy 句柄（真实相机模式）
        self.device_manager = None
        self.gx_cam = None
        self._image_convert = None

        self.video_path = os.getcwd() + "\\test.mp4"  # device_index==999 时的回退视频

    # ------------------------------------------------------------------
    # 登录校验：照搬 usb 版（视觉主程序账号密码通过后才真正开相机）
    # ------------------------------------------------------------------
    def LoginDev(self):
        username = "admin"
        password = "ding123456"
        if self.username == username and self.password == password:
            if self.device_index in (self.available_cameras_index or []) or self.device_index == 999:
                return 0
            else:
                return 2
        else:
            return 1

    # ------------------------------------------------------------------
    # 打开相机
    # ------------------------------------------------------------------
    def open_camera(self):
        # 999 = 视频文件回退模式（无需相机/SDK，离线联调用）
        if self.device_index == 999:
            self._open_video_file()
            return

        if not _GX_AVAILABLE:
            print("ERROR: 未找到 gxipy（大恒 Galaxy Python SDK）。请先安装 Galaxy SDK 并注册 gxipy，"
                  "或将 '大恒图像资料/Development/Samples/Python' 加入 PYTHONPATH。")
            self.is_opened = False
            return

        try:
            self.device_manager = gx.DeviceManager()
            dev_num, dev_info_list = self.device_manager.update_all_device_list()
            if dev_num == 0:
                print("未枚举到大恒相机设备（确认相机已上电、驱动已装、GenTL 已注册）")
                self.is_opened = False
                return

            gx_index = self.device_index + 1  # Galaxy 1-based；device_index=0 -> 第1台
            if gx_index > dev_num:
                print(f"设备索引越界：请求第 {gx_index} 台，实际枚举到 {dev_num} 台")
                self.is_opened = False
                return

            self.gx_cam = self.device_manager.open_device_by_index(gx_index)
            print(f"已打开大恒相机：{dev_info_list[0].get('model_name', '?')} (device_index={self.device_index})")

            # 关自动、设固定曝光/增益/白平衡（固定安装工业相机求稳定）
            self._apply_camera_params(self.gx_cam)

            # 连续采集（非触发）
            try:
                self.gx_cam.TriggerMode.set("Off")
            except Exception:
                pass

            # 图像格式转换对象（Bayer -> RGB）
            self._image_convert = self.device_manager.create_image_format_convert()

            # 开流
            self.gx_cam.stream_on()

            # 验证：取一帧确认链路通
            test_frame = self._grab_bgr()
            if test_frame is None:
                print("开流后未能取到帧，请检查相机状态")
                self.is_opened = False
                return
            self.height, self.width = test_frame.shape[:2]
            self.is_opened = True
            print(f"大恒相机已就绪，分辨率={self.width}x{self.height}")
        except Exception as e:
            print(f"打开大恒相机失败: {e}")
            self.is_opened = False

    def _apply_camera_params(self, cam):
        """逐项设置并 try 包裹：不同相机特性名/支持度差异不致整体失败。"""
        if not GALAXY_AUTO_EXPOSURE:
            try:
                cam.ExposureAuto.set("Off")
            except Exception:
                pass
            try:
                cam.ExposureTime.set(GALAXY_EXPOSURE_TIME_US)
            except Exception:
                pass
        if not GALAXY_AUTO_GAIN:
            try:
                cam.GainAuto.set("Off")
            except Exception:
                pass
            try:
                cam.Gain.set(GALAXY_GAIN_DB)
            except Exception:
                pass
        if not GALAXY_AUTO_WHITE_BALANCE:
            try:
                cam.BalanceWhiteAuto.set("Off")
            except Exception:
                pass

    def _open_video_file(self):
        self.capture = cv2.VideoCapture(self.video_path)
        if not self.capture.isOpened():
            print(f"无法打开视频文件, 路径: {self.video_path}")
            self.is_opened = False
        else:
            self.width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.is_opened = True
            print(f"视频文件已成功打开, 路径: {self.video_path}")

    # ------------------------------------------------------------------
    # 取一帧（对外统一返回 BGR numpy 数组 或 None）
    # ------------------------------------------------------------------
    def get_frame(self):
        if not self.is_opened:
            print("摄像头未打开，无法获取帧！")
            return None

        if self.device_index == 999:
            return self._get_frame_video_file()

        return self._grab_bgr()

    def _grab_bgr(self):
        """从大恒相机取一帧并转成 BGR（cv2/YOLO 需要的通道顺序）。"""
        try:
            raw_image = self.gx_cam.data_stream[0].get_image(timeout=1000)
            if raw_image is None:
                return None
            if raw_image.frame_data.status != GxFrameStatusList.SUCCESS:
                return None

            pf = raw_image.get_pixel_format()
            if pf == GxPixelFormatEntry.RGB8:
                # 已是 RGB8：get_numpy_array 返回 RGB 布局
                rgb = raw_image.get_numpy_array()
            else:
                # Bayer/其他：经 ImageFormatConvert 转成 RGB8
                conv = self._image_convert
                conv.set_dest_format(GxPixelFormatEntry.RGB8)
                conv.set_valid_bits(_get_best_valid_bits(pf))
                buf_size = conv.get_buffer_size_for_conversion(raw_image)
                out_arr = (c_ubyte * buf_size)()
                conv.convert(raw_image, addressof(out_arr), buf_size, False)
                rgb = numpy.frombuffer(out_arr, dtype=numpy.ubyte, count=buf_size).reshape(
                    raw_image.frame_data.height, raw_image.frame_data.width, 3)

            if rgb is None:
                return None
            # 关键：大恒出的是 RGB，cv2/YOLO 需要 BGR，必须翻转通道（漏掉颜色就反）
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            return bgr
        except Exception as e:
            print(f"获取帧失败: {e}")
            return None

    def _get_frame_video_file(self):
        if self.capture is None or not self.capture.isOpened():
            print("视频未打开")
            return None
        ret, frame = self.capture.read()
        if not ret:
            # 循环播放
            self.capture.release()
            self.capture = cv2.VideoCapture(self.video_path)
            ret, frame = self.capture.read()
            if not ret:
                return None
        return frame

    # ------------------------------------------------------------------
    # 枚举相机（返回 0-based 索引列表，与 usb 版语义一致）
    # ------------------------------------------------------------------
    def list_connected_cameras(self):
        if not _GX_AVAILABLE:
            return []
        try:
            dm = gx.DeviceManager()
            dev_num, _ = dm.update_all_device_list()
            self.available_cameras_index = list(range(dev_num))
            return self.available_cameras_index
        except Exception as e:
            print(f"枚举相机失败: {e}")
            return []

    # ------------------------------------------------------------------
    # 关闭相机
    # ------------------------------------------------------------------
    def close_camera(self):
        if self.device_index == 999:
            if self.capture:
                self.capture.release()
                self.capture = None
            self.is_opened = False
            print("视频文件已关闭")
            return

        try:
            if self.gx_cam is not None:
                self.gx_cam.stream_off()
                self.gx_cam.close_device()
        except Exception as e:
            print(f"关闭相机异常: {e}")
        self.gx_cam = None
        self.device_manager = None
        self._image_convert = None
        self.is_opened = False
        print("大恒相机已关闭")


if __name__ == "__main__":
    # 自测：device_index=0 接真实相机；device_index=999 播放 test.mp4
    cam = Camera(device_index=0)
    cam.open_camera()
    if cam.is_opened:
        while True:
            frame = cam.get_frame()
            if frame is not None:
                cv2.imshow("Galaxy Camera", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        cam.close_camera()
    cv2.destroyAllWindows()
