# 测试版本
import fnmatch
import json
import os
import sys
import time
import numpy as np
import torch
from PyQt5 import uic
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from floating_subtitle_test import FloatingCaption
from FontSet import Setting
from PLC1 import plc_thread
from cameraV4 import videoProcessingThread
from camera_control_usb import Camera
from viusalPage import ViusalPage

class PlatForm(QMainWindow):
    # 线程生命区
    videoThread = videoProcessingThread()
    # videoThread2 = videoProcessingThread2()

    # 信号
    detectSignal = pyqtSignal(bool)
    trackSignal = pyqtSignal(bool)
    targetID = pyqtSignal(object)
    floatingCaptionSignal = pyqtSignal(bool)
    ViusalPageTextSignal = pyqtSignal(bool)
    # 发送图片
    imageFile = pyqtSignal(object)
    # 单独图片发送信号
    camera_signal = pyqtSignal(bool)
    # 打开问答管理系统的信号
    qa_signal = pyqtSignal()
    float_caption = pyqtSignal(str)

    def __init__(self):
        super(PlatForm, self).__init__()
        # 这么写的原因时因为海康的API中更改了工作目录
        # print(os.getcwd())

        self.BeiBei_text_start_time = None
        self.ui = uic.loadUi("configs/ui_files/platform.ui")
        # self.visiualUI = uic.loadUi("configs/ui_files/page.ui")
        self.visiualUI = ViusalPage()

        # 获取ui设置
        self.detectedVideo = self.ui.video
        self.detectButton = self.ui.detectButton
        self.textBrowser = self.ui.textBrowser
        self.lineEdit = self.ui.lineEdit
        self.settingButton = self.ui.settingButton
        self.visiualButton = self.ui.visiualButton
        self.randomMatchButton = self.ui.trackButton_2
        self.faceMatchButton = self.ui.trackButton_3
        # self.prioriFaceMatchButton = self.ui.trackButton_4
        self.plc_button = self.ui.plcButton
        # 摄像头控制按钮
        # 外置可视化页面
        # self.detectedVideo2 = self.visiualUI.video
        self.ImagLabel = self.ui.ImagLabel

        # 发送信号
        # 字幕
        self.ViusalPageTextSignal.connect(self.change_text_running)
        self.detectSignal.connect(self.videoThread.change_running)

        self.targetID.connect(self.videoThread.chage_id)
        self.randomMatchButton.clicked.connect(self.randomID)  # 随机id
        self.targetFlag = 0  # 随机目标跟踪符号，0为默认模式，1为随机ID模式，2为输入指定图片模式，3为默认图片模式
        self.randomFlag = False  # 随机匹配FLAG
        self.imageFlag = False  # 随机输入图像进行匹配
        self.imageFile.connect(self.videoThread.chage_imagefile)
        # self.imageFile.connect(self.videoThread.change_itemfile)
        # # 开启物品识别
        # video_thread.change_itemfile("path/to/item/image.jpg")
        # # 关闭物品识别
        # video_thread.change_itemfile(None)

        self.videoThread.update_detection.connect(self.updateDetected)
        # self.camera_signal.connect(self.videoThread2.ChangeRunning)

        # 字体及参数设置
        self.settingButton.clicked.connect(self.saveSet)

        # 接受来自camera信号
        self.camera_index = 0
        # 传画面
        self.videoThread.update_detected_frame.connect(self.updateDetectedFrame_slot)
        self.videoThread.update_frame.connect(self.updateDetectedFrame_slot2)
        # 传识别到的ID信号，这两个信号可以放到一起
        self.videoThread.update_detectedIDs.connect(self.updateDetectedIDs_slot)
        self.videoThread.target_signal.connect(self.signal_process)
        self.videoThread.face_target.connect(self.face_target_display)

        # 重置ID
        self.videoThread.camera_log.connect(self.printMessage)

        # 来自ui控件
        # 视觉
        self.detectButton.clicked.connect(self.detectOpenClose)
        self.lineEdit.returnPressed.connect(self.updateID)
        # self.trackButton.clicked.connect(self.trackOpenClose)
        self.visiualButton.clicked.connect(self.visiualPageOpen)
        self.faceMatchButton.clicked.connect(self.imageMatch)

        self.plc_button.clicked.connect(self.plc_getip_and_start)
        # 摄像头云台控制
        # self.CamUPButton.clicked.connect(self.cam_ctrl_up)
        # self.CamDownButton.clicked.connect(self.cam_ctrl_down)
        # self.CamLeftButton.clicked.connect(self.cam_ctrl_left)
        # self.CamRightButton.clicked.connect(self.cam_ctrl_right)
        self.speed = 5
        self.sleeptime = 1

        # 北北字幕，字幕显示帧数是BeiBei_text_count_thread(模拟没秒的帧数) * 说话时间，达标归为None
        # 文字直接发给self.viusalUI.text
        self.BeiBei_text = None
        # 每秒有多少帧
        self.BeiBei_text_count_thread = 16
        # 总计时器
        self.BeiBei_text_count = 0
        # 录音有多长
        self.BeiBei_text_time = 0
        # 改录音有几段
        self.BeiBei_text_length = 0
        # 每段文字显示时间BeiBei_text_time // length
        self.BeiBei_text_lengthtime = 0
        # 设置中文字体

        # ids
        self.ids = None
        self.id = 0
        self.CamCtrl = None
        self.detectFalseCount = 0  # 未检测到的次数
        self.detectFalseCount_thre = 30
        self.detectFalseCount_thre_time = 10

        # 图像为匹配次数
        self.image_match_tolerance = 0
        self.image_match_thre = 10
        self.image_match_thre_time = 5

        # 目标未识别到
        self.person_lost_tolerance = 0
        self.person_lost_thre = 20
        self.person_lost_thre_time = 5
        # 避免丢失tolerance匹配到人物后又丢失，tolerance信号累加
        self.person_confirm = 0
        self.person_confirm_thre = 10

        self.initUI()
        # 控制文本输出
        self.initTextBrowser()
        # 初始化字体
        # 字体，具体数据格式产参见font.json文件
        self.setting = None
        self.initSet()
        # 初始的字幕显示为True
        self.floating_caption = FloatingCaption()
        self.floating_caption.update_text("---")

        self.floatingCaptionSignal.emit(True)
        self.ViusalPageTextSignal.emit(True)
        self.VisiualPageText_is_enabled = False

        self.ui.setWindowIcon(QIcon(os.getcwd() + "//configs//pics//bear.png"))

        self.last_id = None

        # 初始化plcThread为None
        self.plcThread = None

        # ========== 新增：人物属性识别相关 ==========song
        # 1. 连接属性识别信号
        self.videoThread.update_person_attributes.connect(self.update_attributes_display)
        self.videoThread.attributes_analysis_status.connect(self.printMessage)

        # 2. 属性显示组件（稍后创建）
        self.attributes_display = None

        # 3. 从设置文件读取配置
        self.load_attributes_config()

    def plc_getip_and_start(self):
        # 用于PLC通信
        self.plcThread = plc_thread(str(self.plc_ip_port["ip"]), int(self.plc_ip_port["port"]))
        self.plcThread.start()
        # plc的包发到主线程
        self.plcThread.send_to_txt_browser.connect(self.plcpacket_to_browser)
        # plc线程状态信息
        # self.plcThread.plcthread_state.connect(self.clear_plcthread)

    def switchNextFunc(self, flag):
        self.showMessage("This switch num" + str(flag))
        if flag == True and self.ids is not None:
            # 随机切换到下一位
            self.randomID_()
            pass

    def closeEvent(self, event):
        # 由于mainwindow不是独立存在，所以closeEvent不会响应
        print("this is closeEvent")
        self.imageFile = False
        self.imageFile.emit(filename)
        showMessage = QMessageBox.question()
        reply = showMessage(self, '警告', "系统将退出，是否确认?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

    def utilSet(self, setting):
        """应用参数"""
        font = QFont(setting["outputFont"]["font"])
        font.setPointSize(setting["outputFont"]["size"])
        font.setItalic(setting["outputFont"]["italic"])
        font.setBold(setting["outputFont"]["bold"])
        self.textBrowser.setFont(font)
        color = QColor(setting["outputFont"]["color"]["R"], setting["outputFont"]["color"]["G"],
                       setting["outputFont"]["color"]["B"])
        self.textBrowser.setTextColor(color)
        # 配置字幕字体设置
        font = QFont(setting["subtitleFont"]["font"])
        font.setPointSize(setting["subtitleFont"]["size"])
        font.setItalic(setting["subtitleFont"]["italic"])
        font.setBold(setting["subtitleFont"]["bold"])
        color = QColor(setting["subtitleFont"]["color"]["R"], setting["subtitleFont"]["color"]["G"],
                       setting["subtitleFont"]["color"]["B"])
        self.visiualUI.setFont(font, color)
        # 按顺序配置视觉参数
        self.videoThread.acc_thre = setting["visual"]["acc_thre"]
        self.targetID.emit(setting["visual"]["target_id"])
        self.detectFalseCount_thre = setting["visual"]["detectFalseCount_thre"]
        self.detectFalseCount_thre_time = setting["visual"]["detectFalseCount_thre_time"]
        self.image_match_thre = setting["visual"]["image_match_thre"]
        self.image_match_thre_time = setting["visual"]["image_match_thre_time"]
        self.person_lost_thre = setting["visual"]["person_lost_thre"]
        self.person_lost_thre_time = setting["visual"]["person_lost_thre_time"]
        # 摄像头参数
        self.speed = setting["camera"]["speed"]
        self.sleeptime = setting["camera"]["sleeptime"]

    def initSet(self):
        # print("font", os.getcwd())
        with open("configs\\settings.json", "r") as file:
            self.setting = json.load(file)
            # 配置字体
            # 配置输出端函数
            self.utilSet(self.setting)

    def saveSet(self):
        # 输出台字体设置
        output_font = self.textBrowser.font()
        output_color = self.textBrowser.textColor()
        setting_dialog = Setting()
        setting_dialog.initUI(output_font, output_color, self.visiualUI.chinese_font, self.visiualUI.color,
                              self.setting)
        # dialog = FontSettingsDialog(self, output_font, output_color, self.visiualUI.chinese_font, self.visiualUI.color)
        if setting_dialog.exec_() == QDialog.Accepted:
            # 更新字体配置
            selected_font, color = setting_dialog.outputSettingsTab.get_selected_font()
            self.textBrowser.setFont(selected_font)
            self.textBrowser.setTextColor(color)
            self.setting["outputFont"]["font"] = selected_font.family()
            self.setting["outputFont"]["size"] = selected_font.pointSize()
            self.setting["outputFont"]["italic"] = selected_font.italic()
            self.setting["outputFont"]["bold"] = selected_font.bold()
            self.setting["outputFont"]["color"]["R"] = color.red()
            self.setting["outputFont"]["color"]["G"] = color.green()
            self.setting["outputFont"]["color"]["B"] = color.blue()

            selected_font, color = setting_dialog.subtitleSettingsTab.get_selected_font()
            self.visiualUI.setFont(selected_font, color)
            self.setting["subtitleFont"]["font"] = selected_font.family()
            self.setting["subtitleFont"]["size"] = selected_font.pointSize()
            self.setting["subtitleFont"]["italic"] = selected_font.italic()
            self.setting["subtitleFont"]["bold"] = selected_font.bold()
            self.setting["subtitleFont"]["color"]["R"] = color.red()
            self.setting["subtitleFont"]["color"]["G"] = color.green()
            self.setting["subtitleFont"]["color"]["B"] = color.blue()

            # 更新字体参数配置
            setting_dialog.setting = self.setting
            # 更新参数配置
            self.setting = setting_dialog.saveSet()
            if self.setting is not None:
                with open('configs\\settings.json', 'w') as file:
                    json.dump(self.setting, file, indent=4)

    def updateDetected(self, data):
        """接收视觉检测数据并发送给PLC"""
        try:
            if self.plcThread and self.plcThread.isRunning():
                self.plcThread.visual_plc_data = data
                # 判断是否有人物锁定
                if self.ids is not None and self.id is not None:
                    # 检查目标ID是否在当前检测到的ID列表中
                    if torch.isin(self.id, self.ids):
                        self.plcThread.vision_lock = 1  # 锁定
                    else:
                        self.plcThread.vision_lock = 0  # 未锁定
                else:
                    self.plcThread.vision_lock = 0  # 未锁定
        except Exception as e:
            self.showMessage("<b>PLC未连接！updateDetected</b>")

    def change_text_running(self, running):
        # 不浮动字幕显示开关
        self.VisiualPageText_is_enabled = running

    def updateDetectedFrame_slot2(self, frame):
        # 将画面传递给外置可视化页面
        if self.visiualUI.isHidden():
            text = self.visiualButton.text()
            if text != "打开可视化页面":
                self.visiualButton.setText("打开可视化页面")
        else:
            self.visiualUI.frame = frame

            self.visiualUI.update()

    def setttingButton(self):
        pixmap = QPixmap("configs\pics\\fontsetting.png")
        self.fontSettingButton.setIcon(QIcon(pixmap))

    def signal_process(self, signal):
        """0为未检测到人型号，1为目标丢失信号，2为图像匹配失败信号，3用于重置目标丢失信号"""
        # 该数值用于返回，一般情况返回0，若某项选择执行到最后一个if就返回该flag
        returnNum = None
        if signal == 0:
            # 该帧未检测到人，已在id类别更新处处理
            self.detectFalseCount += 1
            if self.detectFalseCount % self.detectFalseCount_thre == 0:
                self.showMessage("当前未检测到人体...." + str(self.detectFalseCount // self.detectFalseCount_thre))
                if self.detectFalseCount == self.detectFalseCount_thre * self.detectFalseCount_thre_time:
                    self.showMessage("<b>多次未检测到人体，请排查场景中是否有人体</b>")
                    self.detectFalseCount = 0
                    returnNum = 0
                    # 判断当前打开的是什么功能，关闭这些功能，并随机匹配
                    if self.randomFlag:
                        # 关闭其功能就是在模拟点击动作
                        self.randomMatchButton.click()
                    if self.imageFlag:
                        self.faceMatchButton.click()

        elif signal == 1:
            # 只在不是0的前提下，才肯能会发送1
            # 这里应该还要加一个回复设置，如果匹配到了目标就将其tolerance置回0
            self.person_lost_tolerance += 1
            if self.person_lost_tolerance % self.person_lost_thre == 0:
                self.showMessage("未检测到目标人物...." + str(self.person_lost_tolerance // self.person_lost_thre))
                if self.person_lost_tolerance == self.person_lost_thre * self.person_lost_thre_time:
                    # 判断当前打开的是什么功能，关闭这些功能，并随机匹配
                    if self.randomFlag:
                        # 关闭其功能就是在模拟点击动作
                        self.randomMatchButton.click()
                    if self.imageFlag:
                        self.faceMatchButton.click()

                    self.person_lost_tolerance = 0
                    # 没有考虑id列表为空的情况
                    # 重新筛选信息
                    if (len(self.ids) != 0):
                        self.id = self.ids[0]
                        self.targetID.emit(self.id)
                        self.showMessage("<b>目标已丢失，随机匹配目标ID" + str(int(self.id)) + "</b>")
                    else:
                        self.showMessage("<b>目标已丢失</b>")
                    returnNum = 1

        elif signal == 3:
            # 避免tolerance信号在识别到数据好持续累加
            self.person_confirm += 1
            if self.person_confirm == self.person_confirm_thre:
                self.person_confirm = 0
                self.person_lost_tolerance = 0
                returnNum = 3
        return returnNum

    def pic_find(self):
        """找pics文件夹中是否存有图片，如果没有图片则返回None，如果有多个图片则随意取一个图片"""
        pwd = os.getcwd()
        path = pwd + "\\faces"
        if os.path.exists(path) and os.path.isdir(path):
            pass
        else:
            self.showMessage("默认人脸识别文件夹不存在，请保证项目文件夹中有faces文件夹存在，且存放一张目标人脸照片")
        filename = None
        # 定义图片文件的扩展名
        image_extensions = ['.png', '.jpg', '.jpeg', '.bmp']

        # 遍历当前目录中的文件
        for filename in os.listdir(path):
            # 检查文件扩展名是否在图片扩展名列表中
            if any(filename.lower().endswith(ext) for ext in image_extensions):
                # 返回找到的图片文件的完整路径
                return os.path.join(path, filename)
        # 如果没有找到图片文件，则返回 None
        return None

    def showImage(self, label, pixmap):
        # 在某个label中显示image
        if pixmap.isNull():
            label.setText("Failed to load image.")
            self.showMessage("Failed to load image.")
        else:
            label.setPixmap(pixmap.scaled(label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def find_image_path(self, folder_path, image_number):
        """
        根据输入的数字和文件夹路径，找到对应的图片文件路径。

        :param folder_path: 文件夹路径
        :param image_number: 图片编号（如 1, 2, 3, ...）
        :return: 匹配的图片文件路径，如果没有找到则返回 None
        """
        # 遍历文件夹中的文件
        for filename in os.listdir(folder_path):
            # 使用 fnmatch.fnmatch 来忽略文件扩展名进行匹配
            # 这里假设文件名格式为 "数字.扩展名"，如 "1.jpg", "2.png" 等
            if fnmatch.fnmatch(filename, f"{image_number}.*"):
                # 构建文件的完整路径
                file_path = os.path.join(folder_path, filename)
                return file_path
        # 如果没有找到匹配的文件，则返回 None
        return None

    def face_target_display(self, target_index):
        """只要一次匹配成功就展示，失败则多次匹配接受信号为0
           这里暂时没有发送，signal处理函数已经对多次未匹配进行了处理
           为false则是不存在改图片
        """
        if isinstance(target_index, int):
            pwd = os.getcwd()
            path = pwd + "\\faces"
            face_path = self.find_image_path(path, target_index)
            if face_path == None:
                self.showMessage("faces文件中没有文件" + face_path)
                self.faceMatchButton.click()
                return False
            else:
                self.showMessage("读取图片：" + face_path)
                pixmap = QPixmap(face_path)
                self.showImage(self.ImagLabel, pixmap)
                return True
        else:
            self.showMessage(f"the {target_index} is not index")
            self.faceMatchButton.click()
            return False

    def imageMatch(self):
        """这边发送信号过去，然后接受找到的图片信号"""
        text = self.faceMatchButton.text()
        filename = None
        if text == "打开图像匹配模式":
            self.showMessage("图像匹配模式已打开")
            if self.ids is None:
                self.showMessage("未检测到ID，请重新尝试！！")
                return
            self.randomID_()
            self.showMessage("图像匹配后台运行中，执行一次随机匹配ID")
            self.imageFlag = True
            filename = True
            self.faceMatchButton.setText("关闭图像匹配模式")
        else:
            filename = None
            self.ImagLabel.setText("Image None")
            self.showMessage("图像匹配模式已关闭")
            self.imageFlag = False
            self.faceMatchButton.setText("打开图像匹配模式")
        self.imageFile.emit(filename)
        return filename

    def imageOpen(self, ):
        """用于从文件夹中选择图像"""
        options = QFileDialog.Options()
        filename = None
        # 如果点击取消返回空字符串
        filename, _ = QFileDialog.getOpenFileName(self, "Select Image File", "",
                                                  "Images (*.png *.xpm *.jpg *.jpeg *.bmp *.gif);;All Files (*)",
                                                  options=options)
        if filename == "":
            filename = None
        return filename

    def is_empty_tensor(self, tensor):
        if tensor is None:
            return True
        return tensor.nelement() == 0

    def randomID(self):
        text = self.randomMatchButton.text()
        if self.ids is None or self.is_empty_tensor(self.ids):  # 增加了判定是否为空张量的处理
            self.showMessage("ID 目前为空，请重新尝试！！")
            return
        self.showMessage("进行一次随机匹配")
        flag = self.randomID_()
        if flag != 0:
            self.showMessage("场景中可能无人")
            self.randomMatchButton.click()

    def randomID_(self):  # 1月17日更新，每次取随机数时会避免取到上一次的值，如果有的选的话
        """随机更改id, 0为匹配成功，1为该场景一定时间内为检测到人，2为占位符用于该函数重复执行"""
        # 考虑触发随机ids为空的情况，需要递归处理
        # 考虑目标丢失已经另外处理
        if len(self.ids) != 0:
            remaining_choices = []
            tensor = self.ids.numpy() if isinstance(self.ids, torch.Tensor) else np.array(self.ids)
            if self.last_id == None:
                remaining_choices = tensor
            if len(tensor) == 1:
                remaining_choices = tensor
            else:
                remaining_choices = [num for num in tensor if num != self.last_id]
            self.id = np.random.choice(remaining_choices)

            self.last_id = self.id
            self.targetID.emit(self.id)
            self.printMessage("匹配目标ID" + str(int(self.id)))
            # 退出
            return 0
        else:
            # 匹配到一定次数就弹出
            flag = self.signal_process(0)
            if flag == 0:
                # 空列表上限，打印信息后退出
                return 1
            else:
                # 未上限则继续执行
                return 2

    def visiualPageOpen(self):
        text = self.visiualButton.text()
        if text == "打开可视化页面":
            # self.videoThread2.start()
            if self.videoThread.isRunning() == 0:
                self.showMessage("请先开启检测功能！")
                return
            self.visiualUI.show()
            self.showMessage("可视化页面已打开")
            self.visiualButton.setText("关闭可视化页面")
        else:
            # self.videoThread2.stop()
            self.visiualUI.close()
            self.showMessage("可视化页面已关闭")
            self.visiualButton.setText("打开可视化页面")

    def searchID(self, id):
        """返回True or false"""
        temp = torch.isin(id, self.ids)
        return temp

    def updateID(self):
        """指定目标ID输入功能，当按下返回建和回车建，先判断是否合法，再将其发给cameraThread"""
        id = self.lineEdit.text()
        if not id.isdigit():
            self.printMessage("输入格式错误，请重新输入")
        else:
            self.id = torch.tensor(int(id))
            if self.searchID(self.id):
                # 发送给cam
                self.targetID.emit(self.id)
                self.printMessage("已经匹配目标ID" + str(int(self.id)))
            else:
                self.printMessage(f"输入 ID{self.id} 不在当前id列表中,请重新输入")

    def showMessage(self, message):
        """显示消息到文本浏览器"""
        self.printMessage(message=message)

    def printMessage(self, message):
        """打印带时间戳的消息到文本浏览器"""
        timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
        message = timestamp + " " + message
        self.textBrowser.append(message)

    def initTextBrowser(self):
        """初始化文本浏览器设置"""
        # 设置设置自动换行和垂直和水平滚动
        self.textBrowser.setLineWrapMode(QTextEdit.WidgetWidth)
        self.textBrowser.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.textBrowser.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def print_status(self):
        print("eval(self.videoThread) status\t" + str(self.videoThread.isRunning()))

    def detectOpenClose(self):
        if self.videoThread.isRunning():
            self.detectSignal.emit(False)
            self.detectButton.setText("开始检测")
            self.showMessage("已停止检测")
        else:
            # print(self.videoThread.source)
            self.videoThread.start()
            self.detectSignal.emit(True)
            self.detectButton.setText("停止检测")
            self.showMessage("已开始检测")

    def pause_videoThread(self):
        # 预留接口，如果PLC显示熊正在运动，则暂停视频检测
        pass

    def initUI(self):
        pass

    def updateDetectedFrame_slot(self, frame):
        # 更新检测到的画面到UI
        qimg = QImage(frame.data, frame.shape[1], frame.shape[0], QImage.Format_BGR888)
        pixmap = QPixmap.fromImage(qimg)
        self.detectedVideo.setPixmap(pixmap)

    def updateDetectedIDs_slot(self, new_ids):
        if new_ids is not None:
            # 计算人体数量
            person_count = len(new_ids)

            # 更新检测到的ID列表
            if self.ids is None:
                self.ids = new_ids
            else:
                # 根据数组长度判断大小是否两个数组是否一致
                old_length = len(self.ids)
                new_length = len(new_ids)
                if new_length != old_length:
                    # 不一样就直接赋值
                    self.ids = new_ids
                else:
                    # 一样就进行比对
                    for i in range(old_length):
                        if self.ids[i] != new_ids[i]:
                            self.ids = new_ids
            # 发送人体数量到PLC线程
            if self.plcThread and self.plcThread.isRunning():
                try:
                    self.plcThread.set_person_count(person_count)
                except Exception as e:
                    self.showMessage(f"设置PLC人体数量失败: {e}")
            # 每次ID列表更新时，都检查锁定状态
            self.updateVisionLockStatus()
        else:
            # 如果没有检测到人，设置数量为0
            if self.plcThread and self.plcThread.isRunning():
                try:
                    self.plcThread.set_person_count(0)
                except Exception as e:
                    self.showMessage(f"设置PLC人体数量失败: {e}")

    def updateVisionLockStatus(self):
        """更新视觉锁定状态"""
        try:
            if self.plcThread and self.plcThread.isRunning():
                if self.ids is not None and self.id is not None:
                    # 检查目标ID是否在当前检测到的ID列表中
                    if torch.isin(self.id, self.ids):
                        self.plcThread.vision_lock = 1  # 锁定
                    else:
                        self.plcThread.vision_lock = 0  # 未锁定
                else:
                    self.plcThread.vision_lock = 0  # 未锁定
        except Exception as e:
            self.showMessage("<b>PLC未连接！updateVisionLockStatus</b>")

    def plcpacket_to_browser(self, packet):
        # PLC数据包显示到文本浏览器
        self.printMessage(message=packet)

    # 新属性识别相关代码 song
    def load_attributes_config(self):
        """从配置文件加载属性识别设置"""
        try:
            # 尝试从setting.json读取配置
            if hasattr(self, 'setting') and self.setting.get('person_attributes'):
                config = self.setting['person_attributes']
                model_dir = config.get('model_dir', '')
                #测试代码----------------------》
                # 转换为绝对路径（基于当前工作目录）
                abs_path = os.path.abspath(model_dir)
                print(f"转换后的绝对路径: {abs_path}")

                # 检查路径是否存在
                if os.path.exists(abs_path):
                    print(f"√ 模型路径存在: {abs_path}")
                else:
                    print(f"× 模型路径不存在: {abs_path}")
                # 《----------------------测试代码

                update_interval = config.get('update_interval', 15)
                enabled = config.get('enabled', True)

                # 启用属性识别
                if model_dir and enabled:
                    self.videoThread.enable_attributes_analysis(model_dir)
                    self.videoThread.set_attributes_update_interval(update_interval)
        except Exception as e:
            print(f"加载属性识别配置失败: {e}")

    def update_attributes_display(self, attributes_result):
        """更新属性显示（在主线程中执行）"""
        if attributes_result is None:
            return

        # 1. 创建显示组件（如果不存在）
        if self.attributes_display is None:
            self.create_attributes_display()

        # 2. 更新显示
        self.attributes_display.update_attributes(attributes_result)

        # 3. 发送到PLC（如果已连接）
        self.send_attributes_to_plc(attributes_result)

    def create_attributes_display(self):
        """创建属性显示组件"""
        from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget, QTableWidget, QHeaderView

        # 创建显示面板
        self.attributes_display = QWidget()
        layout = QVBoxLayout(self.attributes_display)

        # 上衣颜色显示
        self.color_label = QLabel("上衣颜色: 等待识别...")
        self.color_label.setStyleSheet("font-weight: bold; color: #333; font-size: 14px;")
        layout.addWidget(self.color_label)

        # 属性表格
        self.attributes_table = QTableWidget()
        self.attributes_table.setColumnCount(3)
        self.attributes_table.setHorizontalHeaderLabels(["属性", "概率", "状态"])
        self.attributes_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.attributes_table.setMaximumHeight(300)
        layout.addWidget(self.attributes_table)

        # 将显示组件添加到主界面
        # 根据你的UI布局，可以选择合适的位置
        # 例如，可以放在textBrowser旁边或visualPage中
        self.ui.layout().addWidget(self.attributes_display)

    def update_attributes_ui(self, result):
        """更新UI显示"""
        if not result:
            return

        summary = result.get('summary', {})
        color_result = result.get('color_result', {})
        attr_result = result.get('attributes_result', {})

        # 1. 更新颜色显示
        if color_result and color_result.get('success'):
            color = color_result.get('final_color', '未知')
            self.color_label.setText(f"上衣颜色: {color}")
            self.color_label.setStyleSheet(
                f"font-weight: bold; color: #e74c3c; font-size: 14px;"
                f"background-color: #f9f9f9; padding: 5px; border-radius: 3px;"
            )

        # 2. 更新属性表格
        if attr_result and attr_result.get('success'):
            probs = attr_result.get('probs', [])
            labels = attr_result.get('labels', [])
            above_threshold = attr_result.get('above_threshold', [])

            self.attributes_table.setRowCount(len(labels))

            for i, (label, prob) in enumerate(zip(labels, probs)):
                # 属性名（中英文）
                chi_label = self.videoThread.attributes_label_map.get(label,
                                                                      label) if self.videoThread.attributes_label_map else label

                # 概率显示
                prob_item = QTableWidgetItem(f"{prob:.1%}")

                # 状态标记
                is_above = i in above_threshold
                status = "✓" if is_above else "✗"
                status_item = QTableWidgetItem(status)

                if is_above:
                    status_item.setForeground(QColor(0, 128, 0))  # 绿色
                    prob_item.setForeground(QColor(0, 128, 0))
                else:
                    status_item.setForeground(QColor(150, 150, 150))  # 灰色
                    prob_item.setForeground(QColor(150, 150, 150))

                self.attributes_table.setItem(i, 0, QTableWidgetItem(chi_label))
                self.attributes_table.setItem(i, 1, prob_item)
                self.attributes_table.setItem(i, 2, status_item)

    def send_attributes_to_plc(self, attributes_result):
        """将属性结果发送到PLC"""
        if not hasattr(self, 'plcThread') or not self.plcThread or not self.plcThread.isRunning():
            return

        try:
            summary = attributes_result.get('summary', {})
            color = summary.get('color', '未知')
            main_attrs = summary.get('main_attributes', [])

            # 将颜色编码为数字（需要与PLC端约定编码规则）
            color_code = self.color_to_code(color)

            # 将主要属性编码（例如，取前3个属性）
            attrs_code = self.attributes_to_code(main_attrs[:3])

            # 扩展PLC数据结构（需要在PLC1.py中添加相应字段）
            # 这里需要根据你的PLC通信协议修改
            if hasattr(self.plcThread, 'person_attributes_data'):
                self.plcThread.person_attributes_data = {
                    'color': color,
                    'color_code': color_code,
                    'attributes': main_attrs,
                    'attributes_code': attrs_code,
                    'timestamp': time.time()
                }

        except Exception as e:
            print(f"发送属性到PLC失败: {e}")

    def color_to_code(self, color):
        """将颜色名称转换为PLC可识别的编码"""
        color_mapping = {
            '红': 1, '黄': 2, '蓝': 3, '绿': 4,
            '黑': 5, '白': 6, '紫': 7, '未知': 0
        }
        return color_mapping.get(color, 0)

    def attributes_to_code(self, attributes):
        """将属性列表转换为编码"""
        # 这里需要根据你的业务逻辑设计编码方案
        # 例如：每个属性对应一个bit位
        attr_mapping = {
            '帽子': 1, '眼镜': 2, '短袖': 4, '长袖': 8,
            '女性': 16, '大于60岁': 32, '18-60岁': 64, '小于18岁': 128
            # ... 添加其他属性
        }

        code = 0
        for attr in attributes:
            if attr in attr_mapping:
                code |= attr_mapping[attr]
        return code


# 登录界面
class Login(QWidget):
    switch_window = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.ui = uic.loadUi("configs/ui_files/login.ui")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        # 登录界面ui控件
        self.index_line = self.ui.index_line
        self.admin_line = self.ui.admin_line
        self.pw_line = self.ui.pw_line
        self.login_button = self.ui.login_button
        # 连接槽
        self.login_button.clicked.connect(self.switchwindow)
        self.ui.setWindowIcon(QIcon(os.getcwd() + "//configs//pics//bear.png"))

    def switchwindow(self):
        self.switch_window.emit()

    def closeEvent(self, event):
        print("this is closeEvent")
        reply = QMessageBox.question(self, '警告', "系统将退出，是否确认?", QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.No)
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()


# 需要把Integrate方法解离，将mainwindow作为主函数触发，这样可以通过触发mainwindow的closeEvnet来保存当下配置
class Integrate(QMainWindow):
    def __init__(self):
        super().__init__()
        self.name = ""
        self.ip = ""
        self.password = ""
        self.init_info = 0
        self.Window = PlatForm()
        # ===== 注释开始：问答系统线程 =====
        # self.qa_thread = QAadmin()
        # ===== 注释结束：问答系统线程 =====
        self.Window.float_caption.connect(self.trans_float_caption)

    def closeEvent(self, event):
        print("this is integrate closeEvent")

    def show_login(self):
        self.login = Login()
        # 第一个执行的函数
        self.login.switch_window.connect(self.show_main)
        self.login.ui.show()

    def show_main(self):
        ##登陆检查
        check_value = self.login_check()
        ##传参
        if check_value == 1:
            self.login.ui.close()
            self.Window.ui.show()
        else:
            print("self", self.init_info)
            if self.init_info == 1:
                self.show_error_popup()
            elif self.init_info == 2:
                self.camera_cannot_find()

    def trans_float_caption(self, float_caption):
        self.floating_caption.show()
        self.floating_caption.update_text(str(float_caption))

    def show_error_popup(self):
        error_popup = QMessageBox(self)
        error_popup.setIcon(QMessageBox.Warning)
        error_popup.setText('请重新输入密码或用户名')
        error_popup.setWindowTitle('登录错误')
        error_popup.setStandardButtons(QMessageBox.Ok)
        error_popup.exec_()

    def camera_cannot_find(self):
        error_popup = QMessageBox(self)
        error_popup.setIcon(QMessageBox.Warning)
        error_popup.setText('未找到摄像头！请检查摄像头是否连接或索引号是否正确')
        error_popup.setWindowTitle('登录错误')
        error_popup.setStandardButtons(QMessageBox.Ok)
        error_popup.exec_()

    def login_check(self):
        # 摄像头登录检查
        self.name = self.login.admin_line.text()
        self.index = self.login.index_line.text()
        self.password = self.login.pw_line.text()

        test = Camera(device_index=self.index, username=self.name, password=self.password)
        available_cameras_index = test.list_connected_cameras()
        print("可用的相机索引编号", available_cameras_index)

        self.init_info = test.LoginDev()
        if self.init_info > 0:
            # 输入错误退出
            return 0
        else:
            self.Window.videoThread.CamInit(self.index)
            del test
            self.floating_caption = FloatingCaption()
            return 1


if __name__ == "__main__":
    app = QApplication(sys.argv)
    plat = Integrate()
    plat.show_login()
    sys.exit(app.exec_())