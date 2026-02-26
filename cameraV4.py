# 基于cameraV2文件改进
# 使用实时编码推流
# 将控制代码去掉

import sys, os
try:
    from person_attributes import PersonAttributes
    PERSON_ATTRIBUTES_AVAILABLE = True
except ImportError as e:
    print(f"警告: 无法导入PersonAttributes模块: {e}")
    PERSON_ATTRIBUTES_AVAILABLE = False

# 在这里添加调试输出
print(f"DEBUG: PERSON_ATTRIBUTES_AVAILABLE = {PERSON_ATTRIBUTES_AVAILABLE}")
print(f"DEBUG: person_attributes 模块路径检查...")

# 检查模块是否存在
import importlib.util
spec = importlib.util.find_spec("person_attributes")
if spec is None:
    print("ERROR: 找不到 person_attributes 模块")
else:
    print(f"DEBUG: person_attributes 模块路径: {spec.origin}")

path = os.getcwd()+"\\YOLOtracker"
sys.path.append(path)
from yolo_queue import YoloQueue
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtCore import QThreadPool, QRunnable, pyqtSlot
import cv2
from datetime import datetime
import time
import numpy as np
import torch
import time
import torch
import cv2
import numpy as np
from ultralytics import YOLO
from YOLOtracker.tracker import Tracker
import face_recognition 
from concurrent.futures import ThreadPoolExecutor
from camera_control_usb import Camera
import gc


class videoProcessingThread(QThread):
    """设置摄像头显示页面"""
    # 该frame用于发送主页面的图像页面
    update_detected_frame = pyqtSignal(object)
    update_detection = pyqtSignal(object)
    camera_log = pyqtSignal(str)
    update_detectedIDs = pyqtSignal(object)
    update_person_attributes = pyqtSignal(dict)  # 发送属性识别结果 Song
    attributes_analysis_status = pyqtSignal(str)  # 发送状态信息 Song
    # 该frame用于发送可视化页面的图像
    update_frame = pyqtSignal(object)
    # 此信号专门用来发送图像匹配未识别、目标丢失、目前无检测人物
    # 如果图像匹配未识别到目标人物，就跳到随机匹配功能
    # 随机匹配如果未识别到人物，就切换到下一个人物，目前切换到下一个人物
    # 0为未检测到人型号，1为目标丢失信号，2为图像匹配失败信号，3用于重置目标丢失信号
    target_signal = pyqtSignal(int)
    face_target = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        print("=== DEBUG: videoProcessingThread.__init__ 被调用 ===")
        print(f"当前工作目录: {os.getcwd()}")

        # 添加CUDA错误计数器
        self.cuda_error_count = 0
        self.max_cuda_errors = 5  # 最多允许5次CUDA错误，然后尝试重启线程
        # 控制参数：是否使用GPU
        self.use_gpu = True  # 默认使用GPU

        # 判断是否有可用的GPU
        self.gpu_available = torch.cuda.is_available()
        if self.gpu_available:
            print(f"检测到GPU: {torch.cuda.get_device_name(0)}")
        else:
            print("未检测到GPU，将使用CPU模式")
            self.use_gpu = False

        # 检查 person_attributes 模块
        print(f"PERSON_ATTRIBUTES_AVAILABLE 状态: {PERSON_ATTRIBUTES_AVAILABLE}")

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.Cam = None
        self.cam_index = 0

        # 目标检测模型，以及配置目标跟踪
        self.tracker = Tracker()
        self.tracker.init_tracker()
        # print(os.getcwd())


        # self.action_model = YOLO("weights\\5_5\\best.pt", verbose=False) 行为识别临时关闭 song
        self.action_model = None  # 添加这一行 行为识别临时关闭 song

        # 设置行为识别读取参数
        self.num_frame = 7
        self.action_label_map = {'0': 'attack', '1': 'cheer up', '2': 'clapping', '3': 'drink and eat', '4': 'hand waving', '5': 'make victory sign',
                                 '6': 'pick up', '7': 'sit down', '8': 'stand', '9': 'taking a selfie', '10': 'thumb up', '11': 'use phone', '12': 'walk'}

        self.running = False

        self.fps_window_size = 10
        # self.target_id = torch.tensor(0)  # 默认为1
        self.target_id = 1
        self.acc_thre = 0.65

        # 识别结果
        self.diff_x = 0
        self.diff_y = 0

        # 图像大小
        self.frame_width = 0
        self.frame_height = 0

        self.imageFile = None
        self.goal_image = None
        self.goal_face_encoding = None
        self.known_face_encodings = None
        self.known_face_names = None
        # 多少帧未检测到人脸就报错，自动切换随机模式（当前版本取消）
        # self.imageMatch_tolerance_thread = 50
        self.imageMatch_success = False

        # 定义阶段检索文件夹储存图片
        self.folder_path = os.getcwd() + "\\faces"
        self.load_known_faces(self.folder_path)
        self.executor = ThreadPoolExecutor(max_workers=1)
        #判断人脸识别进程是否在运行的标志量
        self.is_face_matching = False
        # 定义一下人脸识别线程中发送信息的频率
        self.target_face_match_count = 10
        self.face_match_count = 0
        # 保存上一次人脸识别匹配最接近的量的变量
        self.nearest_face_distance = 100

        # 用以存放该ID第一次识别到的bbox，这个方法只能用来解决抖动问题
        # 如何解决闪屏幕问题，不是需要记这个bbox，而是需要记录这个比例  (嗯，有道理)
        self.bbox_center_x = 0
        self.bbox_center_y = 0
        self.bbox_width = 0
        self.bbox_height = 0
        #此数大于0时，代表有记忆，为0时代表无记忆，大于一定值时不启用可视化界面图片放大函数
        self.memory_cnt = 0
        #保留多少帧的记忆
        self.max_memory_cnt = 18
        # 记录上一次检测到的bbox中心点，小范围的移动不更新bbox框，解决小范围抖动问题
        self.last_bbox_center_x = 0
        self.last_bbox_center_y = 0

        # ========== 新增：人物属性识别相关初始化 ==========song
        # 1. 线程池（用于并行处理）
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(1)  # 只允许一个属性识别线程，避免资源竞争
        # 任务队列监控
        self.pending_attributes_tasks = 0  # 当前待处理的任务数
        self.max_pending_tasks = 2  # 最大允许的待处理任务数

        # 2. 属性识别器（延迟初始化）
        self.attributes_detector = None
        self.attributes_model_dir = ""  # 需要外部设置
        self.attributes_enabled = False  # 是否启用属性识别
        self.attributes_label_map = None  # 标签映射

        # 3. 控制参数
        self.attributes_update_interval = 15  # 每15帧更新一次属性（约0.5秒@30fps）
        self.frame_counter = 0
        self.last_attributes_result = None  # 上一次的识别结果（用于缓存）
        self.last_target_id = None  # 上一次识别的目标ID
        self.attributes_processing = False  # 是否正在处理中（避免重复提交）

        # 4. 性能优化：结果相似度阈值
        self.attributes_similarity_threshold = 0.9  # 结果相似度超过90%时复用上一次结果
        self.last_attributes_time = 0  # 上一次识别的时间戳

        self.attributes_use_cpu = True  # 添加此标志控制是否使用cpu模式

    def CamInit(self, device_index):
        self.Cam = Camera(device_index)
        self.Cam.open_camera()  # 目前主程序是账号密码通过后才会运行这个初始化程序，因此在视觉主程序中打开摄像头
        frame = self.Cam.get_frame()
        self.frame_height, self.frame_width, _ = frame.shape


    # def padding_bboximg(self, img, target_size=640):
    #     width, height, _ = img.shape
    #     # 缩放图片（保持宽高比）
    #     if max(width, height) > target_size:
    #         scaling_factor = target_size / max(width, height)
    #         new_width = int(width * scaling_factor)
    #         new_height = int(height * scaling_factor)
    #         img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
    #
    #         # 计算需要填充的边距
    #     delta_width = target_size - img.shape[1]
    #     delta_height = target_size - img.shape[0]
    #     top, bottom = delta_height // 2, delta_height - (delta_height // 2)
    #     left, right = delta_width // 2, delta_width - (delta_width // 2)
    #
    #     # 填充图片，使其成为 640x640
    #     color = [0, 0, 0]  # 使用黑色进行填充
    #     padded_img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
    #
    #     return padded_img

    def padding_bboximg(self, img, target_size=640):
        width, height, _ = img.shape
        scaled_img = img
        new_width = width
        new_height = height

        # 缩放图片（保持宽高比）
        if max(width, height) > target_size:
            scaling_factor = target_size / max(width, height)
            new_width = int(width * scaling_factor)
            new_height = int(height * scaling_factor)
            scaled_img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)

        # 计算需要填充的边距
        delta_width = target_size - scaled_img.shape[1]
        delta_height = target_size - scaled_img.shape[0]

        # 根据新的宽高比计算边距
        top = delta_height // 2
        bottom = delta_height - top
        left = delta_width // 2
        right = delta_width - left

        # 调整填充的边距以确保目标bbox位于中心位置
        img_height, img_width = scaled_img.shape[:2]
        center_x = self.bbox_center_x * (new_width / width)  # 将原始中心坐标比例应用到新尺寸
        center_y = self.bbox_center_y * (new_height / height)

        # 更新填充位置，使中心点靠近屏幕中心
        start_x = int(center_x) - left
        start_y = int(center_y) - top

        if start_x < 0:
            left += abs(start_x)
            start_x = 0
        if start_y < 0:
            top += abs(start_y)
            start_y = 0

        # 填充图片，使其成为 target_size x target_size
        color = [0, 0, 0]  # 使用黑色进行填充
        padded_img = cv2.copyMakeBorder(scaled_img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)

        return padded_img

    def crop_image(self, img, bboxes):
        """得到xyxy形式的bobox进行裁减并返回"""
        x1 = int(bboxes[0])
        y1 = int(bboxes[1])
        x2 = int(bboxes[2])
        y2 = int(bboxes[3])
        bbox_img = img[y1:y2, x1:x2]
        return bbox_img
    
    def tlwh_to_xyxy(self, bbox, img_size=640):
        "左上角加wh变为左上角加右下角，并返回xcenter和ycenter"
        bbox[0] = int(bbox[0] * self.frame_width / img_size)
        bbox[1] = int(bbox[1] * self.frame_height / img_size)
        bbox[2] = int(bbox[2] * self.frame_width / img_size)
        bbox[3] = int(bbox[3] * self.frame_height / img_size)
        bbox[2]=int(bbox[0] + bbox[2])
        bbox[3]=int(bbox[1] + bbox[3])
        return bbox

        # print(f"已加载 {len(self.known_face_encodings)} 张已知人脸")

    def remember_bbox(self, bbox):
        # 获得目标的bbox后记忆下来 标识符设置为1
        self.memory_cnt = 1
        x_min, y_min, x_max, y_max = bbox
        # bbox的宽度和高度
        self.bbox_width = x_max - x_min
        self.bbox_height = y_max - y_min
        # bbox的中心点
        bbox_center_x = x_min + self.bbox_width // 2
        bbox_center_y = y_min + self.bbox_height // 2
        # 用来计算的中心点
        f_center_x = self.bbox_center_x
        f_center_y = self.bbox_center_y

        delta_x = abs(self.last_bbox_center_x - bbox_center_x)
        delta_y = abs(self.last_bbox_center_y - bbox_center_y)
        if (delta_x <= 3 and delta_y <= 3):
            # 不更新坐标，保持原来的中心点
            self.bbox_center_x = self.last_bbox_center_x
            self.bbox_center_y = self.last_bbox_center_y
        else:
            self.bbox_center_x = bbox_center_x
            self.bbox_center_y = bbox_center_y

    def crop_and_pad_with_gray(self, image, scale=0.5):
        # 获取原图的尺寸和宽高比
        orig_height, orig_width = image.shape[:2]
        aspect_ratio = orig_width / orig_height

        # bbox的宽度和高度
        bbox_width = self.bbox_width
        bbox_height = self.bbox_height
        # bbox的中心点
        center_x = self.bbox_center_x
        center_y = self.bbox_center_y
        # 用来计算的中心点
        f_center_x = self.bbox_center_x
        f_center_y = self.bbox_center_y

        # 最长边大于原图尺寸的一定比例时，不进行裁剪
        if (bbox_width > orig_width * scale) or ( bbox_height > orig_height * scale):
            return image[0:orig_height, 0:orig_width]

        # 计算裁剪区域的半宽和半高（原图的0.5倍尺寸，保持宽高比）
        half_width = int(orig_width * scale / 2)
        half_height = int(half_width / aspect_ratio)



        # 简单做了一个运镜效果的实现
        if self.memory_cnt > self.max_memory_cnt*2/3: #在多次丢失目标后...
            half_width = half_width + (self.memory_cnt - self.max_memory_cnt*2/3) * 35  #我随便编了个数，如果用这个效果的话就改成自适应的
            half_height = int(half_width / aspect_ratio)

        # 计算裁剪区域的边界坐标
        start_x = center_x - half_width
        end_x = center_x + half_width
        start_y = center_y - half_height
        end_y = center_y + half_height

        # 重新计算裁剪区域的边界坐标
        start_x = f_center_x - half_width
        end_x = f_center_x + half_width
        start_y = f_center_y - half_height
        end_y = f_center_y + half_height

        gray_value = [128, 128, 128]  # RGB灰色
        # padded_image = np.full((orig_height, orig_width, 3), gray_value, dtype=np.uint8)
        crop_x_min = int(max(0, start_x))
        crop_x_max = int(min(orig_width, end_x))
        crop_y_min = int(max(0, start_y))
        crop_y_max = int(min(orig_height, end_y))

        # 从原图中裁剪出实际可裁剪的区域，并放置到填充了灰色的图像中
        # padded_image[crop_y_min:crop_y_max, crop_x_min:crop_x_max] = image[max(0, start_y):min(orig_height, end_y), max(0, start_x):min(orig_width, end_x)]

        # 然而，由于我们想要保持原图的宽高比并且裁剪区域已经是这个比例了（只是尺寸缩小了），
        # 我们实际上不需要对actual_crop进行任何进一步的尺寸调整。我们直接返回padded_image中
        # 对应裁剪区域的部分（或者整个padded_image，取决于你的需求）。

        # 为了简化，我们直接返回整个填充了灰色边界的图像，其中包含了裁剪后的实际区域。

        # return padded_image[max(0, start_y - half_height):min(orig_height, end_y + half_height),
        #                     max(0, start_x - half_width):min(orig_width, end_x + half_width)]
        # print(crop_y_min,crop_y_max, crop_x_min,crop_x_max)
        # print("crop_and_pad")
        self.last_bbox_center_x = center_x
        self.last_bbox_center_y = center_y

        return image[crop_y_min:crop_y_max, crop_x_min:crop_x_max]


    def sort_files_by_number(self, file_list):
        """从文件名中提取数字部分并按数字排序"""
        return sorted(file_list, key=lambda x: int(os.path.splitext(x)[0]))  # 提取文件名中的数字部分进行排序


    def load_known_faces(self, folder_path):
        """加载指定文件夹中的所有图片，并提取人脸特征"""
        if not os.path.exists(folder_path):
            print("文件夹不存在:", folder_path)
            return

        self.known_face_encodings = []  # 清空之前的已知人脸特征
        self.known_face_names = []  # 清空之前的已知人脸名称

        # 获取所有文件，并按数字排序
        file_list = [file_name for file_name in os.listdir(folder_path) if file_name.endswith(('jpg', 'png', 'jpeg'))]
        sorted_files = self.sort_files_by_number(file_list)

        for file_name in sorted_files:
            goal_image_path = os.path.join(folder_path, file_name)
            known_image = face_recognition.load_image_file(goal_image_path)
            face_encodings = face_recognition.face_encodings(known_image)

            if face_encodings:
                self.known_face_encodings.append(face_encodings[0])
                self.known_face_names.append(file_name.split('.')[0])  # 使用文件名作为名字
            else:
                print(f"警告: 文件 {file_name} 中没有找到人脸")
        # print("调试信息:  ",self.known_face_names)
        mes = f"已加载 {len(self.known_face_encodings)} 张已知人脸"
        self.camera_log.emit(mes)

    def match_face_thread(self, frame, results):
        """进行人脸匹配，并通过目标检测框匹配到人脸"""
        T_id = False

        # 进行人脸检测
        # 上采样数量越大，越适合处理小人脸  HOG吃CPU，CNN吃GPU，但是更精确
        face_locations = face_recognition.face_locations(frame, number_of_times_to_upsample=1, model="hog")

        face_encodings = face_recognition.face_encodings(frame, face_locations)

        # 标记是否匹配到目标人脸
        found = False
        #记录本轮最接近人脸距离的中间变量
        near_face_distance = 0
        for name, encoding in zip(self.known_face_names, self.known_face_encodings):
            
            # name是下标
            for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
                if len(face_encodings) == 0:
                    return np.empty((0))
                # 计算人脸距离, 距离越小越相似
                face_distance = np.linalg.norm([encoding] - face_encoding, axis=1)
                # print(face_distance)
                if face_distance > near_face_distance:
                    near_face_distance = face_distance
                matches = face_recognition.compare_faces([encoding], face_encoding,tolerance=0.45)

                if True in matches:  # 如果有匹配成功
                    # 找到第一个匹配的位置
                    first_match_index = matches.index(True)
                    name = int(name)
                    center_x = int((left + right) / 2)
                    center_y = int((top + bottom) / 2)

                    # 根据检测框与人脸中心点进行匹配
                    for id, bbox in results.items():
                        if bbox[0] <= center_x <= bbox[2] and bbox[1] <= center_y <= bbox[3]:
                            self.camera_log.emit("图像匹配成功ID"+str(id)+", 相似值为"+str(float(face_distance)))
                            self.face_target.emit(name)
                            self.imageMatch_success = True
                            self.target_id = id
                            T_id = True
                            break  # 只要匹配到一个就结束
                if T_id:
                    break

            if T_id:
                break
        self.nearest_face_distance = near_face_distance
        return T_id

    def start_face_matching(self, frame,results):
        """启动人脸匹配，如果已经在匹配则不执行"""
        if self.is_face_matching:
            return  # 如果正在进行人脸匹配，则直接返回
        
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.is_face_matching = True  # 设置为正在匹配

        # 使用线程池异步调用人脸匹配
        future = self.executor.submit(self.match_face_thread,frame,results)
        future.add_done_callback(self.handle_recognition_result)


    def handle_recognition_result(self, future):
        """处理识别结果，完成后重置标识"""
        match_id = future.result()  # 获取结果
        self.is_face_matching = False  # 重置为不匹配状态
        self.face_match_count += 1
        if match_id is False and self.face_match_count == self.target_face_match_count:
            self.face_match_count = 0
            if self.nearest_face_distance == 0: #压根就没有找到人脸啊
                self.camera_log.emit("人脸识别线程：未匹配到目标人物,上一轮并未发现人脸")
            else:
                self.camera_log.emit("人脸识别线程：未匹配到目标人物,上一轮最接近的相似值为"+str(float(self.nearest_face_distance)))


    def stop_face_thread(self):
        # wait=false 不管线程是否进行完毕都关闭线程池
        # 在主线程的关闭相应函数里面也加了这个
        self.executor.shutdown(wait=False)

    def update_detection_collect(self, results, preds = None):
        """计算目标ID的动作ID相对画面中心的偏移量"""
        for id, bbox in results.items():
            if id == self.target_id:
                # 计算偏移量
                # 0为正，1为负，右为正，左为负，上为正，下为负
                screen_center_x = self.frame_width / 2
                screen_center_y = self.frame_height / 2

                center_x = (bbox[0] + bbox[2]) / 2
                center_y = (bbox[1] + bbox[3]) / 2

                offset_x = int(center_x - screen_center_x)
                offset_y = int(center_y - screen_center_y)

                # 获取动作ID
                if preds is not None:
                    action_id = preds[0].probs.top1
                    # 转换为字符串标签（如果需要）
                    # action_label = self.action_label_map.get(str(action_id), "unknown")
                else:
                    # 禁用行为识别时，发送默认值
                    action_id = 0  # 或者 "stand" 等默认值

                data = (action_id, offset_x, offset_y)
                self.update_detection.emit(data)
                # print(data)   坐标xy轴的log song
                break

        

    def run(self):
        try:
            # 添加这行关键日志
            self.camera_log.emit(f"[属性识别] === videoProcessingThread.run 开始执行 ===")

            # 检查摄像头是否初始化
            if self.Cam is None:
                self.camera_log.emit("[错误] Cam 未初始化，无法运行")
                return

            action_count = 0
            print_label = "recognizing..."
            print_acc = 0
            action_label = ""
            action_label_acc = 0
            fps_label = None
            # max_size参数还需要调整
            action_queue = YoloQueue(max_size=30)
            self.camera_log.emit("默认匹配目标ID"+str(int(self.target_id)))
            image_count = 0

            # 添加属性识别状态变量
            last_attributes_status = self.attributes_enabled

            # fps设置
            fps = 0
            fps_list = []
            prev_time = time.time()
            id = self.target_id
            # count = 1

            if self.Cam is None:
                print("Error! Cam is not Init!")

            consecutive_errors = 0

            # 改正这里self.cam持续输出图片
            while True and self.running:
                try:
                    # 检查属性识别状态变化
                    if self.attributes_enabled != last_attributes_status:
                        last_attributes_status = self.attributes_enabled
                        if self.attributes_enabled:
                            self.camera_log.emit(
                                f"[属性识别] 状态变化：属性识别已启用，更新间隔: {self.attributes_update_interval}帧")
                        else:
                            self.camera_log.emit("[属性识别] 状态变化：属性识别已禁用")
                    # image_count += 1
                    # print(image_count)
                    frame = self.Cam.get_frame()

                    if frame is None:
                        self.camera_log.emit("[警告] 获取帧失败，跳过")
                        continue

                    img = frame.copy()

                    # 推理，检测并跟踪
                    # 这里是对每一帧都进行检测，也可以对连续的图片进行检测
                    # 也可以考虑用yolo的关键点提取方法，因为只识别一个人所以比较简单
                    detect_num, results, ids= self.tracker.yolov8_tracker(frame)

                    # 如果检测失败但帧有效，尝试跳过这一帧继续处理
                    if detect_num is None:
                        self.camera_log.emit("[警告] 检测器返回None，跳过该帧")
                        self.update_detected_frame.emit(frame)
                        self.update_frame.emit(frame)
                        continue

                    # 成功时重置错误计数器
                    consecutive_errors = 0

                    # self.camera_log.emit(
                    #     f"[DEBUG] 检测到 {detect_num} 个人, IDs: {list(ids) if ids is not None else None}")
                    # self.camera_log.emit(f"[DEBUG] 目标ID: {self.target_id}, 类型: {type(self.target_id)}")
                    # if results:
                    #     self.camera_log.emit(f"[DEBUG] results.keys(): {list(results.keys())}")

                    # 每次识别完后都发送id列表
                    self.update_detectedIDs.emit(ids)
                    # 相对画面中心的偏移量实现 定义 右为正，左为负，上为正，下为负

                    # self.camera_log.emit(str(detect_num))
                    if detect_num == 0:
                        #中心点记忆清零
                        self.last_bbox_center_x = 0
                        self.last_bbox_center_y = 0
                        # 在检测不到人类时如果有记忆，就维持这个bboX的参数一段时间
                        if self.memory_cnt > 0: #有上一次bbox的记忆
                            img = self.crop_and_pad_with_gray(img)
                            self.memory_cnt += 1
                            if self.memory_cnt >= self.max_memory_cnt:
                                self.memory_cnt = 0

                        self.target_signal.emit(0)
                        # 如果未识别到就发送空白帧,并跳出循环
                        self.update_detected_frame.emit(frame)
                        self.update_frame.emit(img)
                        continue

                    # 人脸识别确定目标
                    if self.imageMatch_success == False:
                        if self.imageFile != None:
                            # 匹配时不开启行为识别
                            image_match_flag = self.start_face_matching(frame, results)

                            # 匹配时间说明
                            if image_match_flag == False:
                                # self.target_signal.emit(2)
                                continue

                    # 找到对应的目标
                    i = 0
                    target_spotted = False
                    for id, bbox in results.items():
                        # 只有目标丢失后才会触发目标寻找
                        try:
                            if id == self.target_id:
                                target_spotted = True
                                self.remember_bbox(bbox)  #为图像放大记录数据，这里使cnt变为1
                                # color = (B, G, R)
                                color = (0, 0, 255)
                                thickness = 2
                                cv2.rectangle(frame, (int(bbox[0]), int(bbox[1])),
                                    (int(bbox[2]), int(bbox[3])),
                                    color=color, thickness=thickness)
                                cv2.putText(frame, f'ID: {id}', (int(bbox[0]), int(bbox[1] - 10)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color=color, thickness=thickness)
                                # 在外置页面上进行展示
                                color = (0, 100, 255)
                                thickness = 2
                                cv2.rectangle(img, (int(bbox[0]), int(bbox[1])),
                                    (int(bbox[2]), int(bbox[3])),
                                    color=color, thickness=thickness)

                                img = self.crop_and_pad_with_gray(img)
                            else:
                                # 没找到flag +1，并跳出循环进行后续操作
                                i += 1
                                color = (200, 0, 0)
                                thickness = 2
                                cv2.rectangle(frame, (int(bbox[0]), int(bbox[1])),
                                    (int(bbox[2]), int(bbox[3])),
                                    color=color, thickness=thickness)
                                cv2.putText(frame, f'ID: {id}', (int(bbox[0]), int(bbox[1] - 10)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color=color, thickness=thickness)
                                continue
                        except TypeError:
                            break
                        # 是否开启图像匹配
                        # 数据处理
                        # xyxy = self.tlwh_to_xyxy(result.tlwh)
                        # 找到了目标队形
                        self.target_signal.emit(3)
                        xyxy = bbox
                        bbox_img = self.crop_image(frame, xyxy)
                        padded_img = self.padding_bboximg(bbox_img)
                        # 推理 暂时关闭行为识别 sognpeng
                        preds = None
                        # preds = self.action_model(padded_img, device=self.device, verbose=False)
                        # # 标签处理
                        # action_label = self.action_label_map[str(preds[0].probs.top1)]
                        # action_label_acc = preds[0].probs.top1conf.cpu().numpy()
                        # current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        # # print(current_time, "action_label:", action_label, "action_label_acc:", action_label_acc)
                        # # print(f"[{current_time}] action_label: {action_label}, action_label_acc: {action_label_acc}")
                        # if action_label_acc <= self.acc_thre:
                        #     continue
                        # action_preds = [action_label, action_label_acc]
                        # action_queue.enqueue(item=action_preds)
                        #
                        # 传信函数在这里
                        self.update_detection_collect(results,preds)

                    # ========== 新增：在目标检测后添加属性识别 ==========songpeng
                    # 添加属性识别的日志
                    # self.camera_log.emit(
                    #     f"[DEBUG] 属性识别状态: enabled={self.attributes_enabled}, detector={'loaded' if self.attributes_detector else 'not loaded'}")
                    #
                    # if detect_num > 0:
                    #     self.camera_log.emit(
                    #         f"[DEBUG] 当前目标ID {self.target_id} 是否在 results 中: {self.target_id in results}")

                    if detect_num > 0 and self.attributes_enabled and self.target_id  in results:
                        # self.camera_log.emit(
                        #     f"[属性识别] 检测到 {detect_num} 个人，attributes_enabled={self.attributes_enabled}")
                        bbox = results[self.target_id]
                        # self.camera_log.emit(f"[属性识别] 执行属性识别: target_id={self.target_id}")

                        # 执行属性识别（异步）
                        self.analyze_person_attributes(frame, self.target_id, bbox)

                    # 将显示的识别数据和发送的数据分开，可在页面单独显示该画面
                    print_acc = 0.0
                    if action_count == self.num_frame:
                        result = action_queue.find_most_frequent()
                        if result is not None:
                            print_label, print_acc = result
                        else:
                            print_label = "recognizing..."
                            print_acc = 0.0
                        action_count = 0
                    else:
                        action_count += 1


                    if target_spotted == False: #存在bbox，但是不是匹配的目标
                        if self.memory_cnt > 0: #有上一次bbox的记忆
                            img = self.crop_and_pad_with_gray(img)
                            self.memory_cnt += 1
                            if self.memory_cnt >= self.max_memory_cnt:
                                self.memory_cnt = 0
                    # 计算帧率
                    # 记录当前时间
                    curr_time = time.time()
                    fps = 1 / (curr_time - prev_time)
                    prev_time = curr_time
                    # 添加到FPS列表并保持滑动窗口大小
                    fps_list.append(fps)
                    if len(fps_list) > self.fps_window_size:
                        fps_list.pop(0)
                    # 计算平均FPS
                    avg_fps = sum(fps_list) / len(fps_list)

                    # 绘图
                    # 绘制框
                    # 因为上面都是浅拷贝，所以在tracker中的画图在此处有效
                    # 两种情况不画，一是没有识别到人，二是目标人物动作较小
                    if i == detect_num:
                        self.target_signal.emit(1)
                    else:
                        try:
                            if print_acc >= 0.75: #(2.3.2:0.75)
                                fps_label = f'ID{int(self.target_id)} FPS: {int(avg_fps)} + {print_label} + {(print_acc*100):.2f}%'
                                print(fps_label)
                            #else
                            else:
                                # fps_label = "recognizing..."
                                fps_label = f'ID{int(self.target_id)} FPS: {int(avg_fps)} r...: + {print_acc}'
                        except TypeError:
                            fps_label = "recognizing..."
                        # 如果绿色标签没有显示，就是acc_thre给的太高
                        cv2.putText(frame, fps_label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                    # 无论图像是何种都需要将其发送出去，以保证页面的流畅性
                    self.update_detected_frame.emit(frame)
                    img = self.resolution_enhancement(img)
                    self.update_frame.emit(img)
                except Exception as e:
                    error_msg = str(e)
                    # 检查是否为CUDA错误
                    if "CUDA" in error_msg or "cuda" in error_msg:
                        self.cuda_error_count += 1
                        self.camera_log.emit(f"[CUDA错误] 第{self.cuda_error_count}次CUDA错误: {error_msg[:100]}")

                        # 如果CUDA错误过多，尝试切换到CPU模式
                        if self.cuda_error_count >= self.max_cuda_errors and self.use_gpu:
                            self.camera_log.emit("[严重] CUDA错误过多，尝试切换到CPU模式")
                            self.use_gpu = False
                            # 可以在这里添加重启检测线程的逻辑
                    else:
                        self.cuda_error_count = 0  # 非CUDA错误重置计数器
                    self.camera_log.emit(f"[错误] 单帧处理异常: {str(e)}")
                    # 可以选择记录错误但继续运行
                    import traceback
                    error_details = traceback.format_exc()
                    self.camera_log.emit(f"[错误] 详细异常信息:\n{error_details[:200]}...")

                    # 如果连续错误过多，暂停等待系统恢复
                    consecutive_errors += 1
                    if consecutive_errors >= 10:
                        self.camera_log.emit("[严重] 连续错误过多，暂停10秒...")
                        time.sleep(10)
                        consecutive_errors = 0
                    continue
        except Exception as e:
            self.camera_log.emit(f"[错误] run方法异常: {str(e)}")
            import traceback
            error_details = traceback.format_exc()
            self.camera_log.emit(f"[错误] 详细异常信息:\n{error_details}")


            # print("memeory_cnt",self.memory_cnt)

    def resolution_enhancement(self, frame):
        # 使用INTER_LANCZOS4插值方法来增强画质
        enhanced_frame = cv2.resize(frame, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_LANCZOS4)
        return enhanced_frame



            
    # 接受界面传来的信号
    @pyqtSlot(bool)
    def change_running(self, running):
        self.running = running

    @pyqtSlot(object)
    def chage_id(self, id):
        # if not torch.is_tensor(id):
        #     id = torch.tensor(id)
        # self.target_id = id
        """修改目标ID，确保存储为整型"""
        if torch.is_tensor(id):
            self.target_id = int(id.item())
        else:
            self.target_id = int(id)
        self.camera_log.emit(f"目标ID已更新为: {self.target_id} (类型: {type(self.target_id)})")


    def chage_imagefile(self, path):
        """版本更新，path不为None是以表示开启优先级匹配功能，为None则表示关闭优先功能"""
        self.imageFile = path
        # print(str(path))
        if self.imageFile != None:
            # 将标志位置为False以开启人脸识别功能
            self.imageMatch_success = False
        else:
            self.imageMatch_success = True
            self.stop_face_thread()
            pass

    # ========== 新增：属性识别相关方法 ==========song

    def enable_attributes_analysis(self, model_dir, label_map=None):
        self.printMessage("=== DEBUG: enable_attributes_analysis 开始执行 ===")
        self.printMessage(f"当前线程: {QThread.currentThread()}")
        self.printMessage(f"videoThread 状态: {self.videoThread}")

        """启用人物属性识别功能"""
        if not PERSON_ATTRIBUTES_AVAILABLE:
            self.camera_log.emit("警告: PersonAttributes模块不可用，无法启用属性识别")
            return False

        self.attributes_model_dir = model_dir
        self.attributes_label_map = label_map
        self.attributes_enabled = True

        # 延迟初始化识别器（不在此处加载模型）
        self.camera_log.emit("人物属性识别功能已启用（延迟加载模型）")
        return True

    def disable_attributes_analysis(self):
        """禁用人物属性识别功能"""
        self.attributes_enabled = False
        if self.attributes_detector:
            self.attributes_detector = None
        self.camera_log.emit("人物属性识别功能已禁用")

    def _init_attributes_detector(self):
        self.camera_log.emit(f"[属性识别] 初始化检测器，enabled={self.attributes_enabled}")
        """延迟初始化属性识别器"""
        if self.attributes_detector is not None or not self.attributes_enabled:
            return

        try:
            # 使用CPU，避免与YOLO冲突
            use_gpu = not self.attributes_use_cpu  # 根据标志决定

            self.attributes_detector = PersonAttributes(
                model_dir=self.attributes_model_dir,
                label_map=self.attributes_label_map,
                threshold=self.attributes_threshold,  # 可配置阈值
                use_gpu=use_gpu  # 使用GPU加速
            )

            device = "CPU" if not use_gpu else "GPU"
            self.camera_log.emit(f"人物属性识别模型加载成功（{device}模式），阈值为（{self.attributes_threshold}）")
        except Exception as e:
            self.camera_log.emit(f"人物属性识别模型加载失败: {str(e)}")
            self.attributes_detector = None

    def _should_update_attributes(self, target_id, bbox):
        """
        判断是否需要更新属性识别
        基于：帧计数、目标是否变化、是否正在处理中
        """
        # 暂时总是返回 True，确保属性识别被执行
        # self.camera_log.emit(f"[属性识别] _should_update_attributes 被调用，返回 True")

        # 基本检查
        if not self.attributes_enabled or self.attributes_processing:
            return False

        # 每N帧更新一次
        if self.frame_counter % self.attributes_update_interval != 0:
            return False

        # 目标ID变化时需要更新
        if target_id != self.last_target_id:
            return True

        # 检查bbox是否太小（小目标属性识别不准确）
        x1, y1, x2, y2 = bbox
        bbox_width = x2 - x1
        bbox_height = y2 - y1

        # 如果目标太小，不进行属性识别
        if bbox_width < 50 or bbox_height < 100:
            self.camera_log.emit(f"[属性识别] 目标太小({bbox_width}x{bbox_height})，跳过")
            return False

        # 检查bbox是否发生显著变化
        if self.last_attributes_result:
            # 简单通过bbox中心点移动距离判断
            last_x = (self.last_attributes_result.get('bbox', [0, 0, 0, 0])[0] +
                      self.last_attributes_result.get('bbox', [0, 0, 0, 0])[2]) / 2
            last_y = (self.last_attributes_result.get('bbox', [0, 0, 0, 0])[1] +
                      self.last_attributes_result.get('bbox', [0, 0, 0, 0])[3]) / 2
            curr_x = (bbox[0] + bbox[2]) / 2
            curr_y = (bbox[1] + bbox[3]) / 2

            # 如果中心点移动超过一定距离，需要重新识别
            distance = ((curr_x - last_x) ** 2 + (curr_y - last_y) ** 2) ** 0.5
            if distance > 50:  # 移动超过50像素
                return True

        return True  # 默认需要更新

    def _handle_attributes_result(self, result, bbox):
        """处理属性识别结果的回调函数（在UI线程中执行）"""
        self.camera_log.emit(f"[属性识别] === _handle_attributes_result  回调函数开始 ===")

        self.attributes_processing = False

        # 详细检查结果结构
        if not result:
            self.camera_log.emit("[属性识别] 结果为空")
            return

        # 检查结果中是否包含'summary'
        if 'summary' not in result:
            self.camera_log.emit(f"[属性识别] 警告：结果中没有'summary'键")
            self.camera_log.emit(f"[属性识别] 结果包含的键: {list(result.keys())}")

            # 尝试查看结果的其他部分
            if 'color_result' in result:
                self.camera_log.emit(f"[属性识别] color_result: {result['color_result']}")
            if 'attributes_result' in result:
                self.camera_log.emit(f"[属性识别] attributes_result: {result['attributes_result']}")

            # 如果结果中没有'summary'，我们仍然可以尝试处理，但需要小心
            # 或者可以直接返回，不发送到UI
            # return  # 暂时注释掉，继续处理看看

        # 1. 缓存结果
        result['bbox'] = bbox  # 添加bbox信息
        result['timestamp'] = time.time()
        self.last_attributes_result = result
        self.last_attributes_time = time.time()

        # 2. 发送到主界面
        try:
            self.update_person_attributes.emit(result)
            self.camera_log.emit("[属性识别] 结果已发送到UI")
        except Exception as e:
            self.camera_log.emit(f"[属性识别] 发送结果到UI失败: {e}")

        # 3. 可选：在日志中显示摘要
        if result.get('color_result', {}).get('success') or result.get('attributes_result', {}).get('success'):
            summary = result['summary']
            color = summary.get('color', '未知')
            attrs_count = len(summary.get('main_attributes', []))
            self.camera_log.emit(f"属性识别: 上衣{color}, {attrs_count}个显著属性")

    def analyze_person_attributes(self, frame, target_id, bbox):

        # 增加帧计数器
        self.frame_counter += 1

        """
        分析指定目标的人物属性
        在视频处理循环中调用此方法
        """
        # self.camera_log.emit(f"[属性识别] === analyze_person_attributes 开始 ===")
        # self.camera_log.emit(f"[属性识别] 目标ID={target_id}, bbox={bbox}")
        # self.camera_log.emit(f"[属性识别] 属性识别启用状态: {self.attributes_enabled}")
        # self.camera_log.emit(f"[属性识别] 属性识别器状态: {self.attributes_detector is not None}")
        # self.camera_log.emit(f"[属性识别] 是否正在处理: {self.attributes_processing}")

        # 检查是否应该更新
        if not self._should_update_attributes(target_id, bbox):
            # self.camera_log.emit(f"[属性识别] _should_update_attributes 返回 False")
            return

        # 检查是否有太多待处理任务
        if self.pending_attributes_tasks >= self.max_pending_tasks:
            self.camera_log.emit(f"[属性识别] 有{self.pending_attributes_tasks}个待处理任务，跳过")
            return

        # 确保识别器已初始化
        self._init_attributes_detector()
        if self.attributes_detector is None:
            self.camera_log.emit("[属性识别] 属性识别器未初始化，跳过识别")
            return

        # 标记为处理中
        self.attributes_processing = True
        self.last_target_id = target_id

        # 增加待处理任务计数
        self.pending_attributes_tasks += 1
        self.camera_log.emit(f"[属性识别] 创建并提交属性识别任务，当前任务数: {self.pending_attributes_tasks}")

        def task_callback(result, bbox):
            """包装的回调函数，确保任务计数减少"""
            try:
                # 调用原始的业务逻辑
                self._handle_attributes_result(result, bbox)
            except Exception as e:
                self.camera_log.emit(f"[属性识别] 处理结果时出错: {e}")
            finally:
                # 无论如何都减少任务计数
                self.pending_attributes_tasks = max(0, self.pending_attributes_tasks - 1)
                self.camera_log.emit(f"[属性识别] 任务完成，剩余任务: {self.pending_attributes_tasks}")

        # 创建工作线程任务
        worker = AttributesAnalysisWorker(
            attributes_detector=self.attributes_detector,
            image=frame,
            bbox=bbox,
            callback=task_callback
        )

        # 提交到线程池
        self.thread_pool.start(worker)

    # ========== 新增：供外部调用的方法 ==========song
    @pyqtSlot(bool)
    def set_attributes_enabled(self, enabled):
        self.camera_log.emit(f"[属性识别] set_attributes_enabled 被调用: {enabled}")
        """设置属性识别启用状态"""
        self.attributes_enabled = enabled
        if not enabled and self.attributes_detector:
            self.attributes_detector = None
            self.camera_log.emit("属性识别已禁用")

    @pyqtSlot(str)
    def set_attributes_model_dir(self, model_dir):
        """设置属性识别模型路径"""
        self.attributes_model_dir = model_dir
        # 重置检测器，以便下次重新加载
        if self.attributes_detector:
            self.attributes_detector = None
            self.camera_log.emit(f"属性模型路径已更新: {model_dir}")

    @pyqtSlot(int)
    def set_attributes_update_interval(self, interval):
        """设置属性识别更新间隔（帧数）"""
        if interval >= 5:  # 最小间隔5帧，避免性能问题
            self.attributes_update_interval = interval
            self.camera_log.emit(f"属性识别更新间隔改为每{interval}帧")

    @pyqtSlot(float)
    def set_attributes_threshold(self, threshold):
        """设置属性识别阈值"""
        if hasattr(self, 'attributes_detector') and self.attributes_detector:
            self.attributes_detector.THRESHOLD = threshold
            self.camera_log.emit(f"属性识别阈值改为{threshold}")
        else:
            # 先保存，初始化时再应用
            self.attributes_threshold = threshold

    def get_attributes_status(self):
        """获取属性识别状态"""
        return {
            'enabled': self.attributes_enabled,
            'detector_loaded': self.attributes_detector is not None,
            'update_interval': self.attributes_update_interval,
            'processing': self.attributes_processing,
            'last_result': self.last_attributes_result is not None
        }

    def set_attributes_use_cpu(self, use_cpu):
        """设置是否使用CPU进行属性识别"""
        self.attributes_use_cpu = use_cpu
        # 重置检测器，以便重新加载
        if self.attributes_detector:
            self.attributes_detector = None
        self.camera_log.emit(f"属性识别将使用{'CPU' if use_cpu else 'GPU'}")


# ==================== 新增：属性识别工作线程 ====================
class AttributesAnalysisWorker(QRunnable):
    """用于在后台线程执行属性识别的Runnable"""

    def __init__(self, attributes_detector, image, bbox, callback):
        super().__init__()
        self.attributes_detector = attributes_detector
        self.image = image.copy()  # 深拷贝，避免线程间数据竞争
        self.bbox = bbox
        self.callback = callback

    @pyqtSlot()
    def run(self):
        """在工作线程中执行属性识别"""
        try:
            # 1. 截取目标区域
            x1, y1, x2, y2 = map(int, self.bbox)
            person_img = self.image[y1:y2, x1:x2]

            if person_img.size == 0:
                if self.callback:
                    self.callback(None, self.bbox)
                return

            # 2. 执行属性识别（耗时操作）
            result = self.attributes_detector.analyze_full(
                person_img,
                analyze_color=True,
                analyze_attributes=True
            )

            # 3. 回调主线程
            if self.callback:
                self.callback(result, self.bbox)

        except Exception as e:
            print(f"属性识别线程错误: {str(e)}")
            # 即使出错也调用回调，确保任务计数减少
            if self.callback:
                self.callback(None, self.bbox)

if __name__ == "__main__":
    video = videoProcessingThread()
    video.CamInit(device_index = 1)
    frame = video.Cam.get_frame()
    cv2.imshow("test", frame)
    while True:
        frame = video.Cam.get_frame()
        cv2.imshow("test", frame)
        if cv2.waitKey(1) & 0xff == ord("q"):
            break