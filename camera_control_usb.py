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

    def open_camera(self,):
        """打开 USB 摄像头"""
        self.capture = cv2.VideoCapture(self.device_index)
        if self.device_index == 999:
            self.capture = cv2.VideoCapture(self.video_path)
            if not self.capture.isOpened():
                print(f"无法打开视频文件, 路径: {self.video_path}")
                self.is_opened = False
            else:
                print(f"视频文件已成功打开, 路径: {self.video_path}")
                self.is_opened = True


        if not self.capture.isOpened():
            print(f"无法打开 USB 摄像头, 设备索引: {self.device_index}")
            self.is_opened = False
        else:
            print(f"USB 摄像头已成功打开, 设备索引: {self.device_index}")
            # 设置摄像头的分辨率
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            # self.capture.set(cv2.CAP_PROP_BRIGHTNESS, 64)
            # self.capture.set(cv2.CAP_PROP_FPS, 30)
            self.capture.set(cv2.CAP_PROP_EXPOSURE, -4)
            # self.capture.set(cv2.CAP_PROP_AUTO_WB, 1)
            self.capture.set(cv2.CAP_PROP_GAIN, 13.0)
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
        """获取一帧图像"""
        if not self.is_opened:
            print("摄像头未打开，无法获取帧！")
            return None

        ret, frame = self.capture.read()
        if not ret:
            print("无法获取帧")
            if self.device_index == 999:  # 如果是视频文件，重置视频到开头
                self.capture.release()
                self.capture = cv2.VideoCapture(self.video_path)
                self.is_opened = True
                ret, frame = self.capture.read()  # 尝试再次读取帧
                if not ret:
                    print(f"无法重新打开视频文件, 路径: {self.video_path}")
                    self.is_opened = False
                    return None
            else:
                return None
        return frame


    def list_connected_cameras(self):
        i = 0
        index = 0
        available_cameras = []
        max_attempts = 3  # 很笨的一个方法，防止代码试相机编号的时候报错，但是报错了其实也没什么...
        attempts = 0  # 当前尝试次数

        while attempts < max_attempts:
            cap = cv2.VideoCapture(i)
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