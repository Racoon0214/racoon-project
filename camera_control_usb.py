import os
import time
import cv2


class Camera:
    def __init__(self, device_index=0, username=None, password=None):
        # 先把账号密码临时放到这里
        self.username = username
        self.password = password

        self.device_index = int(device_index)
        self.width = 1920
        self.height = 1080
        self.capture = None
        self.is_opened = False
        # 2026-10-16 取帧容错状态：治 MSMF 长时会话失效"无法获取帧"刷屏
        self.reconnect_attempts = 0          # 连续取帧失败计数
        self.max_reconnect_attempts = 5      # 连续失败超过该值则停止重试(防死循环烧 CPU)
        self._fatal_logged = False           # 是否已打印"停止重试"提示(避免刷屏)
        self.available_cameras_index = None

        self.video_path = os.getcwd() + "\\test.mp4"  # 假设视频文件在当前目录下



    def LoginDev(self):  # 对海康登录函数的拙劣模仿
        # 怎么加密呢...
        username = "admin"
        password = "ding123456"

        if self.username == username and self.password == password:
            if self.device_index in self.available_cameras_index or self.device_index == 999:
                # self.open_camera()  目前用到这个的就是一个登陆界面 所以不用开摄像头了
                return 0

            else:  # 设备索引不在可用的摄像头列表中
                return 2
        else:  # 登陆错误
            return 1

    def _apply_uvc_params(self):
        """2026-10-16 抽离：open_camera 与 get_frame 自动重连都需重新设置（新 capture 参数会重置）。
        ===== UVC(普通USB摄像头) 曝光/增益 调参说明 =====
        【核心语义与大恒一致：让画面更亮(暗光)/更暗(防过曝)。UVC 的"数值方向"和"范围"因摄像头驱动而异，
        以下为 Windows UVC 最常见约定，以现场实测为准。】
        关键前提：手动曝光/增益【只有在关闭自动曝光后才真正生效】。多数 UVC 默认 AUTO_EXPOSURE=开，
        此时手动值会被自动覆盖(也是之前"画面闪烁"的相机层根因之一)。关自动后建议也固定白平衡。
        注：个别驱动对 AUTO_EXPOSURE 语义不同(可能用 0.25/0.75 或 1=手动)，需现场实测确认。"""
        # 设置摄像头的分辨率
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        # 曝光（UVC 多数用对数刻度，手动范围常见 -13 ~ -1）：-1=自动；手动时越接近-1越亮、越负越暗。当前-4中等偏亮。
        self.capture.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)   # 关自动曝光，使下方手动 EXPOSURE=-4 真正生效
        self.capture.set(cv2.CAP_PROP_EXPOSURE, -4)
        # 白平衡：关自动后颜色固定、属性识别颜色更一致；相机用默认白平衡点，若现场偏色再手动设 RGB gain。
        self.capture.set(cv2.CAP_PROP_AUTO_WB, 0)
        # 增益（UVC 范围常见 0~100 或 0~255）：调大更亮但放大噪声；当前13.0低增益。仅曝光拉满仍偏暗才上调。
        self.capture.set(cv2.CAP_PROP_GAIN, 13.0)

    def open_camera(self,):
        """打开 USB 摄像头（2026-10-16 改：默认用 CAP_DSHOW 后端，长时稳定性优于默认的 MSMF）"""
        if self.device_index == 999:
            # 视频文件测试模式
            self.capture = cv2.VideoCapture(self.video_path, cv2.CAP_DSHOW)
            if not self.capture.isOpened():
                print(f"无法打开视频文件, 路径: {self.video_path}")
                self.is_opened = False
            else:
                print(f"视频文件已成功打开, 路径: {self.video_path}")
                self.is_opened = True
            return

        self.capture = cv2.VideoCapture(self.device_index, cv2.CAP_DSHOW)
        if not self.capture.isOpened():
            print(f"无法打开 USB 摄像头, 设备索引: {self.device_index}")
            self.is_opened = False
            return
        print(f"USB 摄像头已成功打开(DSHOW), 设备索引: {self.device_index}")
        self._apply_uvc_params()
        self.is_opened = True


    # def get_frame(self):
    #     """获取一帧图像"""
    #     if not self.is_opened:
    #         print("摄像头未打开，无法获取帧！")
    #         return None
    #
    #     ret, frame = self.capture.read()
    #     if not ret:
    #         print("无法获取帧")
    #         return None
    #     return frame

    def get_frame(self):
        """获取一帧图像（2026-10-16 改：取帧失败自动重连 + 日志降噪，治 MSMF 长时会话失效刷屏）"""
        if not self.is_opened:
            # 已停止重试：仅首次提示，避免每帧刷屏
            if not self._fatal_logged:
                print("[取帧容错] 摄像头已停止重试，请检查硬件或重启程序。")
                self._fatal_logged = True
            return None

        ret, frame = self.capture.read()
        if ret:
            return frame

        # ===== 取帧失败：进入自动重连流程 =====
        if self.device_index == 999:  # 视频文件：重置到开头
            self.capture.release()
            self.capture = cv2.VideoCapture(self.video_path, cv2.CAP_DSHOW)
            if self.capture.isOpened():
                self.is_opened = True
                ret, frame = self.capture.read()
                if ret:
                    return frame
            self.is_opened = False
            self._fatal_logged = True
            print(f"无法重新打开视频文件, 路径: {self.video_path}")
            return None

        # 真实 USB 摄像头：自动重连，带次数上限防死循环烧 CPU
        self.reconnect_attempts += 1
        if self.reconnect_attempts == 1:
            print(f"[取帧容错] 取帧失败，尝试自动重连(最多{self.max_reconnect_attempts}次)...")
        if self.reconnect_attempts > self.max_reconnect_attempts:
            print(f"[取帧容错] 重连{self.max_reconnect_attempts}次仍失败，停止重试。")
            self.is_opened = False
            self._fatal_logged = True
            return None
        try:
            self.capture.release()
        except Exception:
            pass
        self.capture = cv2.VideoCapture(self.device_index, cv2.CAP_DSHOW)
        if self.capture.isOpened():
            self._apply_uvc_params()  # 新 capture 需重新设置分辨率/曝光/增益
            self.is_opened = True
            ret, frame = self.capture.read()
            if ret:
                print("[取帧容错] 摄像头重连成功，恢复取帧。")
                self.reconnect_attempts = 0
                return frame
        # 重连后仍未取到帧：返回 None，下一帧继续尝试（受 max_reconnect_attempts 约束）
        return None


    def list_connected_cameras(self):
        i = 0
        index = 0
        available_cameras = []
        max_attempts = 3  # 很笨的一个方法，防止代码试相机编号的时候报错，但是报错了其实也没什么...
        attempts = 0  # 当前尝试次数

        while attempts < max_attempts:
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)   # 2026-10-16 改：与取帧统一用 DSHOW 后端，避免索引不一致
            if cap.isOpened():
                available_cameras.append(index)
                index += 1
                cap.release()
            else:
                break

            attempts += 1

            i += 1

        self.available_cameras_index = available_cameras
        return available_cameras

    def close_camera(self):
        """关闭 USB 摄像头"""
        if self.capture:
            self.capture.release()
            self.is_opened = False
            print("USB 摄像头已关闭")


if __name__ == "__main__":
    usb_camera = Camera(device_index=1)  # 设备索引可根据实际情况修改
    usb_camera.open_camera()
    while True:
        frame = usb_camera.get_frame()
        if frame is not None:
            cv2.imshow("USB Camera", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):  # 按下 'q' 键退出
            break

    usb_camera.close_camera()
    cv2.destroyAllWindows()