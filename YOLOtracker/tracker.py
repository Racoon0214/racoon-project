import sys, os

import numpy as np
import torch
import cv2

# trackers
from .trackers.byte_tracker import ByteTracker
from .trackers.sort_tracker import SortTracker
from .trackers.botsort_tracker import BotTracker
from .trackers.c_biou_tracker import C_BIoUTracker
from .trackers.ocsort_tracker import OCSortTracker
from .trackers.deepsort_tracker import DeepSortTracker
import gc

# YOLOv8 modules
try:
    from ultralytics import YOLO
    from yolov8_utils.postprocess import postprocess as postprocess_yolov8

except Exception as e:
    print('Load yolov8 fail. If you want to use yolov8, please check the installation.')
    pass

TRACKER_DICT = {
    'sort': SortTracker,
    'bytetrack': ByteTracker,
    'botsort': BotTracker,
    'c_bioutrack': C_BIoUTracker,
    'ocsort': OCSortTracker,
    'deepsort': DeepSortTracker
}

class Tracker():

    def __init__(self):
        self.obj='../jin.mp4' #or camera

        self.detector = 'yolov8' #被我改没用了
        self.tracker = 'ocsort'
        self.reid_model = 'deepsort'
        self.kalman_format = 'ocsort'
        self.img_size = 1280  # 2026-10-16 高清广角版：640->1280(32倍数)，高清检测，远距小目标(20-30m人形)召回更稳；喂原始帧由ultralytics自身letterbox，不再手工缩放
        self.device = '0'

        self.conf_thresh = 0.35  # 2026-10-16 高清广角版：0.5->0.35，兜底更远处小目标(与高清方向一致)；锁定目标不受影响
        self.nms_thresh = 0.3
        self.iou_thresh = 0.3


        self.detector_model_path= './weights/yolov8s.pt'
        #ocsort没用过这两个 不过别的会用到
        self.reid_model_path = './weights/osnet_x1_0.pth'
        self.dhn_path = './weights/DHN.pth'

        self.discard_reid = False #discard reid model, only work in bot-sort etc. which need a reid part
        self.track_buffer = 100
        self.gamma =0.1 #param to control fusing motion and apperance dist
        self.min_area = 300 #use to filter small bboxs

        # 流输入修改为图片输入的过渡变量
        self.last_detect_result = None
        self.tracker_class = None
        self.model_class = None


    def init_tracker(self):
        # 一会这里也写一个
        self.tracker_class = TRACKER_DICT[self.tracker](self)

        if self.detector == 'yolov8':
            print(f"loading detector {self.detector} checkpoint {self.detector_model_path}")
            self.model_class = YOLO(self.detector_model_path)
        else:
            print(f"detector {self.detector} is not supprted")
            exit(0)



    def yolov8_tracker(self, srcImage):
        try:
            frame = srcImage
            h, w, _ = frame.shape
            results = {}
            ids = []

            # 2026-10-16 高清广角版：坐标链路重构(严谨版)
            # 不再手工 letterbox/拉伸 + 手动回投(旧方案存在双重letterbox / imgsz元组顺序错位风险)。
            # 直接把【原始 BGR 帧 frame】交给 YOLO，由 ultralytics 内部自己做 letterbox，
            # 推理后 results 的框已自动反算回【原图像素坐标】 -> postprocess 返回的即原图坐标，零手动变换。
            # imgsz 用单个整数(无 h/w 元组顺序歧义)。
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # 仅供 OCSort.update 外观特征/可视化，不参与检测预处理
            output = None

            try:
                device = '0' if torch.cuda.is_available() else 'cpu'
                with torch.no_grad():
                    # 直接喂原始 BGR 帧；imgsz 显式指定 32 倍数，防止被 ultralytics 缩回默认 640
                    output = self.model_class.predict(frame, conf=self.conf_thresh, iou=self.nms_thresh,
                                                      classes=0, verbose=False, imgsz=self.img_size, device=device)
            except RuntimeError as cuda_error:
                if "CUDA" in str(cuda_error) or "cuda" in str(cuda_error):
                    print(f"[Tracker] CUDA错误，尝试清理缓存: {str(cuda_error)[:100]}")
                    if torch.cuda.is_available():
                        try:
                            torch.cuda.empty_cache()
                        except:
                            pass
                    print(f"[Tracker] CUDA错误，切换到CPU模式: {str(cuda_error)[:100]}")
                    if hasattr(self.model_class, 'model'):
                        self.model_class.model.to('cpu')
                    with torch.no_grad():
                        output = self.model_class.predict(frame, conf=self.conf_thresh, iou=self.nms_thresh,
                                                          classes=0, verbose=False, imgsz=self.img_size, device='cpu')
                else:
                    print(f"[Tracker] 非CUDA错误: {str(cuda_error)[:100]}")
                    return 0, {}, torch.Tensor([])
            if output is not None:
                # Postprocess output to original scales
                output = postprocess_yolov8(output)                     #output才是bboxes
                # detect_num = output.numel() // 6    song
                detect_num = output.numel() // 6 if output.numel() > 0 else 0
            else:
                detect_num = 0
                output = None

            # Convert to tlwh format and update tracker
            if detect_num == 0: # 如果检测器没有检测到目标...
                # print("没找到，目前的处理是不处理，显示原图")
                outputs = None
                # outputs = self.last_detect_result
            elif self.tracker_class is None:
                outputs = None
                print("未初始化跟踪器")
            else:
                if isinstance(output, torch.Tensor):
                    output = output.detach().cpu().numpy()
                output[:, 2] -= output[:, 0]
                output[:, 3] -= output[:, 1]

                outputs = self.tracker_class.update(output, img, frame)
                self.last_detect_result = outputs

            if outputs is not None:
                # Draw results on the frame
                for trk in outputs:
                    bbox = trk.tlwh
                    id = trk.track_id
                    ids.append(id)
                    cls = trk.category
                    score = trk.score

                    # 2026-10-16 高清广角版：postprocess 返回的框已是【原图像素坐标】(ultralytics 内部 letterbox 自动反算)，无需任何手动缩放/回投，直接 tlwh->xyxy。
                    # x_center = int(bbox[0] + bbox[2] / 2)
                    # y_center = int(bbox[1] + bbox[3] / 2)
                    # bbox[2]=int(bbox[0] + bbox[2])
                    # bbox[3]=int(bbox[1] + bbox[3])
                    # results[id] = bbox

                    # 转换为xyxy格式用于存储
                    bbox_xyxy = [
                        int(bbox[0]),
                        int(bbox[1]),
                        int(bbox[0] + bbox[2]),
                        int(bbox[1] + bbox[3])
                    ]
                    results[id] = bbox_xyxy

            # print("detect_num\t", detect_num)
            return detect_num, results, torch.Tensor(ids)

        except Exception as e:
            # 其他异常，也返回空结果
            print(f"[Tracker] 推理过程中所有恢复尝试失败，返回空结果: {str(e)[:100]}")
            return 0, {}, torch.Tensor([])