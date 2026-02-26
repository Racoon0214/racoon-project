# 基于cameraV2文件改进
# 使用实时编码推流
# 将控制代码去掉
import sys, os
path = os.getcwd()+"\\YOLOtracker"
sys.path.append(path)
from yolo_queue import YoloQueue
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
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

class videoProcessingThread(QThread):
    """设置摄像头显示页面"""
    # 该frame用于发送主页面的图像页面
    update_detected_frame = pyqtSignal(object)
    update_detection = pyqtSignal(object)
    camera_log = pyqtSignal(str)
    update_detectedIDs = pyqtSignal(object)
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
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.Cam = None
        self.cam_index = 0

        # 目标检测模型，以及配置目标跟踪
        self.tracker = Tracker()
        self.tracker.init_tracker()
        # print(os.getcwd())
        self.action_model = YOLO("weights\\5_5\\best.pt", verbose=False)
        # self.action_model = YOLO("weights\\4_28\\best.pt", verbose=False)
        # self.action_label_map={'0': 'phone call', '1': 'take off jacket', '2': 'hand waving', '3': 'cheer up', 
        #                        '4': 'jump up', '5': 'play with phone', '6': 'sit down', 
        #           '7': 'squat down', '8': 'stand', '9': 'taking a selfie', '10': 'walk'}
        # 设置行为识别读取参数
        self.num_frame = 7
        # self.action_label_map = {'0': 'cheer_up', '1': 'hand_waving', '2':'jump_up', '3': 'phone_call', '4': 'pick_up','5':'play_with _phone',
        #                          '6':'sit_down', '7': 'squat_down', '8':'stand', '9':'taking_a_selfie', '10':'walk'}
        self.action_label_map = {'0': 'attack', '1': 'cheer up', '2': 'clapping', '3': 'drink and eat', '4': 'hand waving', '5': 'make victory sign',
                                 '6': 'pick up', '7': 'sit down', '8': 'stand', '9': 'taking a selfie', '10': 'thumb up', '11': 'use phone', '12': 'walk'}

        self.running = False

        self.fps_window_size = 10
        self.target_id = torch.tensor(0)  # 默认为1
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

    def update_detection_collect(self, results, preds):
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
                action_id = preds[0].probs.top1


                data = (action_id, offset_x, offset_y)
                self.update_detection.emit(data)
                print(data)
                break

        

    def run(self):
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

        # fps设置
        fps = 0
        fps_list = []
        prev_time = time.time()
        id = self.target_id
        # count = 1
        
        if self.Cam is None:
            print("Error! Cam is not Init!")
        
        # 改正这里self.cam持续输出图片
        while True and self.running:
            # image_count += 1
            # print(image_count)
            frame = self.Cam.get_frame()
            img = frame.copy()
            # 推理，检测并跟踪
            # 这里是对每一帧都进行检测，也可以对连续的图片进行检测
            # 也可以考虑用yolo的关键点提取方法，因为只识别一个人所以比较简单
            detect_num, results, ids= self.tracker.yolov8_tracker(frame)

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
                # 推理
                preds = self.action_model(padded_img, device=self.device, verbose=False)
                # 标签处理
                action_label = self.action_label_map[str(preds[0].probs.top1)]
                action_label_acc = preds[0].probs.top1conf.cpu().numpy()
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # print(current_time, "action_label:", action_label, "action_label_acc:", action_label_acc)
                print(f"[{current_time}] action_label: {action_label}, action_label_acc: {action_label_acc}")
                if action_label_acc <= self.acc_thre:
                    continue
                action_preds = [action_label, action_label_acc]
                action_queue.enqueue(item=action_preds)

                # 传信函数在这里
                self.update_detection_collect(results,preds)

                # 将显示的识别数据和发送的数据分开，可在页面单独显示该画面
                print_acc = 0.0
                if action_count == self.num_frame:
                    print_label, print_acc = action_queue.find_most_frequent()
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
        if not torch.is_tensor(id):
            id = torch.tensor(id)
        self.target_id = id


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