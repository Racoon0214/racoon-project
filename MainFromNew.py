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


# 解决 OpenMP 运行时冲突
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

# 打印当前路径
print(f"当前工作目录: {os.getcwd()}")
print(f"Python 路径: {sys.path}")

# 检查 person_attributes 模块是否存在
person_attributes_path = os.path.join(os.getcwd(), "person_attributes.py")
print(f"person_attributes.py 路径: {person_attributes_path}")
print(f"文件是否存在: {os.path.exists(person_attributes_path)}")

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
    label_name_map = {
        'Female': '女性',
        'AgeOver60': '60岁以上',
        'AgeLess18': '18岁以下',
        'Age18-60': '18-60岁',
        'Hat': '帽子',
        'Glasses': '眼镜',
        'ShortSleeve': '短袖',
        'LongSleeve': '长袖',
        'UpperStride': '上衣条纹',
        'UpperLogo': '上衣Logo',
        'UpperPlaid': '上衣格子',
        'UpperSplice': '上衣拼接',
        'LowerStripe': '下身条纹',
        'LowerPattern': '下身图案',
        'LongCoat': '长外套',
        'Trousers': '长裤',
        'Shorts': '短裤',
        'Skirt&Dress': '裙子',
        'boots': '靴子',
        'HandBag': '手提包',
        'ShoulderBag': '单肩包',
        'Backpack': '双肩包',
        'HoldObjectsInFront': '正面持物',
        'Front': '朝向:前',
        'Side': '朝向:侧',
        'Back': '朝向:后'
    }

    def __init__(self):
        super(PlatForm, self).__init__()
        # 这么写的原因时因为海康的API中更改了工作目录

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
        # 属性识别按钮 song
        self.attributesButton = self.ui.itemMatchButton  # 重命名以明确用途
        self.attributesButton.setText("开启属性识别")  # 初始文本
        self.attributesButton.clicked.connect(self.toggle_attributes_analysis)
        self.cpuModeCheckbox = self.ui.cbCPU
        self.cpuModeCheckbox.setChecked(False)
        self.cpuModeCheckbox.stateChanged.connect(self.set_attributes_cpu_mode)

        #属性识别测试
        self.testAttributesButton = self.ui.TestButton_1  # 重命名以明确用途
        self.testAttributesButton.setText("属性识别的测试")  # 初始文本
        self.testAttributesButton.clicked.connect(self.test_attributes_analysis)
        # 添加测试模式标志
        self.test_mode = False

        # 初始化属性识别状态变量
        self.attributes_enabled = False  # 跟踪属性识别是否启用

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

        # 添加线程状态检查
        self.printMessage(f"初始化时视频线程状态: isRunning={self.videoThread.isRunning()}")
        self.printMessage(f"视频线程 ID: {id(self.videoThread)}")



    def plc_getip_and_start(self):
        # 用于PLC通信
        # self.plcThread = plc_thread(str(self.plc_ip_port["ip"]), int(self.plc_ip_port["port"]))

        self.plcThread = plc_thread('169.254.251.233.1.1', 851)
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
        with open("configs\\settings.json", "r", encoding='utf-8') as file:  # 添加 encoding='utf-8'
            self.setting = json.load(file)
            self.utilSet(self.setting)
        # with open("configs\\settings.json", "r") as file:
        #     self.setting = json.load(file)
        #     # 配置字体
        #     # 配置输出端函数
        #     self.utilSet(self.setting)

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

            # ========== 新增：应用人物属性识别配置 ==========
            if "person_attributes" in self.setting:
                pa_config = self.setting["person_attributes"]

                # 更新视频线程的配置
                model_dir = pa_config.get("model_dir", "")
                if model_dir:
                    # 转换为绝对路径
                    if not os.path.isabs(model_dir):
                        abs_model_dir = os.path.join(os.getcwd(), model_dir)
                        if os.path.exists(abs_model_dir):
                            model_dir = abs_model_dir
                        else:
                            self.printMessage(f"警告: 属性识别模型路径不存在: {abs_model_dir}")

                    self.videoThread.set_attributes_model_dir(model_dir)

                update_interval = pa_config.get("update_interval", 150)
                threshold = pa_config.get("threshold", 0.7)

                self.videoThread.set_attributes_update_interval(update_interval)
                self.videoThread.set_attributes_threshold(threshold)

                # 如果属性识别已启用，确保视频线程的启用状态
                if pa_config.get("enabled", False):
                    self.videoThread.set_attributes_enabled(True)
                else:
                    self.videoThread.set_attributes_enabled(False)

                # 如果UI中属性识别已开启，更新按钮状态
                if self.attributes_enabled and not pa_config.get("enabled", False):
                    # 如果配置中禁用了，但UI是开启状态，提示用户
                    self.printMessage("注意: 配置文件中禁用了属性识别功能")
                    # 可以在这里添加逻辑关闭UI上的属性识别功能

            # ========== 新增结束 =======

            if self.setting is not None:
                with open('configs\\settings.json', 'w', encoding='utf-8') as file:  # 添加 encoding='utf-8' song
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

        # 如果正在开启属性识别，先询问用户song
        if self.attributes_enabled:
            reply = QMessageBox.question(self, '功能冲突',
                                         '属性识别功能已开启，是否先关闭属性识别？',
                                         QMessageBox.Yes | QMessageBox.No,
                                         QMessageBox.Yes)
            if reply == QMessageBox.Yes:
                # 关闭属性识别
                self.disable_attributes_analysis()
                self.attributesButton.setText("开启属性识别")
                self.attributesButton.setStyleSheet("")
                self.attributes_enabled = False

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
        self.printMessage(f"=== DEBUG 1: 点击检测按钮前，videoThread.isRunning() = {self.videoThread.isRunning()}")
        self.printMessage(f"=== DEBUG 2: videoThread 对象: {self.videoThread}")
        if self.videoThread.isRunning():
            self.printMessage("=== DEBUG 3: 正在停止线程")
            self.detectSignal.emit(False)
            self.detectButton.setText("开始检测")
            self.showMessage("已停止检测")
        else:
            self.printMessage("=== DEBUG 4: 正在启动线程")
            # print(self.videoThread.source)
            self.videoThread.start()
            self.printMessage(f"=== DEBUG 5: 线程启动后，isRunning() = {self.videoThread.isRunning()}")
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
            self.printMessage("属性识别结果为空，跳过UI更新")
            return

        # 1. 如果属性识别功能未开启，忽略结果（重要！）
        if not hasattr(self, 'attributes_enabled') or not self.attributes_enabled:
            # 如果收到结果但功能已关闭，可能之前的任务还在运行
            self.printMessage("属性识别功能未启用，跳过UI更新")
            return

        # # 1. 创建显示组件（如果不存在）
        # if self.attributes_display is None:
        #     self.create_attributes_display()

        # # 2. 更新显示
        # self.attributes_display.update_attributes(attributes_result)
        # 2. 更新UI（你已有的代码部分）
        try:
            # 2. 检查结果结构
            if not isinstance(attributes_result, dict):
                self.printMessage(f"属性识别结果不是字典类型: {type(attributes_result)}")
                return

            # 3. 更新UI
            summary = attributes_result.get('summary', {})
            if summary is None:
                summary = {}
            color = summary.get('color', '未知')
            main_attrs = summary.get('main_attributes', [])
            if main_attrs is None:
                main_attrs = []

            # # 更新颜色标签
            if hasattr(self, 'color_label') and self.color_label:
                self.color_label.setText(f"上衣颜色: {color}")

            # 更新属性表格等...
            # 设置颜色标签的背景色（根据颜色名称）
            color_styles = {
                '红': 'background-color: #ffcccc; color: #cc0000;',
                '蓝': 'background-color: #cce5ff; color: #0066cc;',
                '绿': 'background-color: #ccffcc; color: #006600;',
                '黄': 'background-color: #ffffcc; color: #666600;',
                '黑': 'background-color: #666666; color: #ffffff;',
                '白': 'background-color: #ffffff; color: #333333; border: 1px solid #ccc;',
                '紫': 'background-color: #e6ccff; color: #6600cc;',
                '未知': 'background-color: #f0f0f0; color: #666;'
            }
            style = color_styles.get(color, 'background-color: #f0f0f0; color: #333;')
            self.color_label.setStyleSheet(
                f"font-weight: bold; font-size: 11pt; padding: 5px; border-radius: 3px; {style}")

            # # 显示显著特征（最多3个）
            # if main_attrs:
            #     attrs_text = "、".join(main_attrs[:3])
            #     if len(main_attrs) > 3:
            #         attrs_text += f" 等{len(main_attrs)}个"
            #     self.key_attributes_label.setText(f"显著特征: {attrs_text}")
            # else:
            #     self.key_attributes_label.setText("显著特征: 无明显特征")

            # 更新详细表格
            if hasattr(self, 'attributes_table') and self.attributes_table:
                attr_result = attributes_result.get('attributes_result', {})

                # 如果attr_result为None，清空表格
                if attr_result is None:
                    self.attributes_table.setRowCount(0)
                    self.attributes_table.clearContents()
                    self.printMessage("属性识别结果中没有attributes_result字段")
                # 如果attr_result是字典且成功
                elif isinstance(attr_result, dict) and attr_result.get('success'):
                    probs = attr_result.get('probs', [])
                    labels = attr_result.get('labels', [])
                    above_threshold = attr_result.get('above_threshold', [])

                    # 确保数据有效
                    if probs is None:
                        probs = []
                    if labels is None:
                        labels = []
                    if above_threshold is None:
                        above_threshold = []

                    # ========== 重置表格：完全清空 ==========
                    self.attributes_table.setRowCount(0)
                    self.attributes_table.setRowCount(len(labels))  # 重新设为26行

                    # 只关注这四个属性（后续可以逐步添加）
                    target_attributes = ['Age18-60', 'AgeLess18', 'AgeOver60', 'Female', 'Hat', 'Glasses', 'HandBag', 'ShoulderBag', 'Backpack']

                    # 设置表格行数
                    row_count = len(labels)
                    self.attributes_table.setRowCount(row_count)

                    # 如果有标签映射，使用它
                    if hasattr(self.videoThread, 'attributes_label_map') and self.videoThread.attributes_label_map:
                        label_map = self.videoThread.attributes_label_map
                    else:
                        label_map = {}

                        # 填充表格
                        for i in range(min(len(labels), len(probs))):

                            # 属性名（中英文）
                            label = labels[i]

                            # if label not in ['Age18-60', 'AgeLess18', 'AgeOver60', 'Female', 'Hat', 'Glasses']:
                            if label not in target_attributes:
                                continue  # 跳过非目标属性

                            chi_label = label_map.get(label, label) if label_map else label

                            # 概率显示
                            prob = probs[i] if i < len(probs) else 0
                            prob_item = QTableWidgetItem(f"{prob:.1%}")

                            # 状态标记
                            is_above = i in above_threshold
                            status = "✓" if is_above else "✗"
                            status_item = QTableWidgetItem(status)

                            # 创建属性名单元格
                            chi_label = self.label_name_map.get(chi_label, chi_label)  # 英文标签换中文标签
                            label_item = QTableWidgetItem(chi_label)

                            # 设置样式
                            if is_above:
                                status_item.setForeground(QColor(0, 128, 0))  # 绿色
                                prob_item.setForeground(QColor(0, 128, 0))
                                label_item.setForeground(QColor(0, 0, 0))
                            else:
                                status_item.setForeground(QColor(150, 150, 150))  # 灰色
                                prob_item.setForeground(QColor(150, 150, 150))
                                label_item.setForeground(QColor(150, 150, 150))

                            self.attributes_table.setItem(i, 0, label_item)
                            self.attributes_table.setItem(i, 1, prob_item)
                            self.attributes_table.setItem(i, 2, status_item)

                            # ========== 修复：更新表格后重新设置列宽 ==========
                            # 设置第一列的宽度为其他列的两倍
                            base_width = 30  # 基础宽度
                            increased_width = int(base_width * 2)  # 第一列宽度是其他列的两倍

                            # 重新设置列宽
                            self.attributes_table.setColumnWidth(0, increased_width)  # 第一列
                            self.attributes_table.setColumnWidth(1, base_width)  # 第二列
                            self.attributes_table.setColumnWidth(2, base_width)  # 第三列

                            # 确保列宽调整模式正确
                            self.attributes_table.horizontalHeader().setStretchLastSection(False)
                            self.attributes_table.horizontalHeader().setSectionResizeMode(0,
                                                                                          QHeaderView.Fixed)  # 第一列固定宽度
                            self.attributes_table.horizontalHeader().setSectionResizeMode(1,
                                                                                          QHeaderView.Fixed)  # 第二列固定宽度
                            self.attributes_table.horizontalHeader().setSectionResizeMode(2,
                                                                                          QHeaderView.Fixed)  # 第三列固定宽度
                        # ========== 在这里插入删除空白行的代码 ==========
                        row = self.attributes_table.rowCount() - 1
                        while row >= 0:
                            if not self.attributes_table.item(row, 0) or not self.attributes_table.item(row,
                                                                                                        0).text():
                                self.attributes_table.removeRow(row)
                            row -= 1
                        # ========== 临时代码结束 ==========
                else:
                    # 属性识别失败，清空表格
                    self.attributes_table.setRowCount(0)
                    self.attributes_table.clearContents()


        except Exception as e:
            self.printMessage(f"更新属性UI时出错: {e}")
            # 继续执行，UI失败不影响PLC

        # 3. 发送到PLC（如果已连接）
        self.send_attributes_to_plc(attributes_result)

    def create_attributes_display(self):
        """创建属性显示面板（方案一：侧边栏属性面板）"""
        from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QTableWidget,
                                     QHeaderView, QGroupBox, QPushButton, QHBoxLayout)

        # 创建主容器
        self.attributes_display = QWidget()
        main_layout = QVBoxLayout(self.attributes_display)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # 1. 标题栏（可折叠）
        title_layout = QHBoxLayout()
        self.attributes_title = QLabel("人物属性分析")
        self.attributes_title.setStyleSheet("font-weight: bold; font-size: 12pt; color: #333;")

        # 折叠/展开按钮（可选）
        self.toggle_attributes_btn = QPushButton("▲")
        self.toggle_attributes_btn.setFixedSize(20, 20)
        self.toggle_attributes_btn.clicked.connect(self.toggle_attributes_panel)

        title_layout.addWidget(self.attributes_title)
        title_layout.addStretch()
        title_layout.addWidget(self.toggle_attributes_btn)
        main_layout.addLayout(title_layout)

        # 2. 关键信息区域
        key_info_group = QGroupBox("关键属性")
        key_layout = QVBoxLayout(key_info_group)

        # 上衣颜色显示（突出显示）
        self.color_label = QLabel("上衣颜色: --")
        self.color_label.setStyleSheet("font-weight: bold; font-size: 11pt; padding: 5px;")
        key_layout.addWidget(self.color_label)

        # 显著特征标签
        self.key_attributes_label = QLabel("显著特征: --")
        self.key_attributes_label.setWordWrap(True)
        key_layout.addWidget(self.key_attributes_label)

        main_layout.addWidget(key_info_group)

        # 3. 详细属性表格
        detail_group = QGroupBox("详细属性")
        detail_layout = QVBoxLayout(detail_group)

        # 创建表格
        self.attributes_table = QTableWidget()
        self.attributes_table.setColumnCount(3)
        self.attributes_table.setHorizontalHeaderLabels(["属性", "概率", "状态"])


        # self.attributes_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # 设置列宽：第一列增加50%，第二列和第三列自适应
        self.attributes_table.horizontalHeader().setStretchLastSection(False)
        self.attributes_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)  # 第一列拉伸
        self.attributes_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 第二列自适应
        self.attributes_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 第三列自适应

        # 设置初始列宽比例（可选）
        # 计算增加50%后的宽度
        base_width = 100  # 基础宽度
        increased_width = int(base_width * 2)  # 增加50%

        # 设置最小宽度
        self.attributes_table.setColumnWidth(0, increased_width)  # 第一列
        self.attributes_table.setColumnWidth(1, base_width)  # 第二列
        self.attributes_table.setColumnWidth(2, base_width)  # 第三列

        self.attributes_table.setMaximumHeight(250)  # 限制高度，可滚动
        self.attributes_table.verticalHeader().setVisible(False)  # 隐藏行号
        # 设置为Interactive模式，允许用户调整
        # self.attributes_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)

        detail_layout.addWidget(self.attributes_table)
        main_layout.addWidget(detail_group)

        # 将属性面板添加到主界面
        # 这里需要根据你的实际UI布局决定放在哪里
        # 建议放在左侧控制区的下方
        self.ui.verticalLayout_6.insertWidget(1, self.attributes_display)  # 示例位置

        # 初始状态：展开
        self.attributes_panel_expanded = True


    # def update_attributes_ui(self, result):
    #     """更新UI显示"""
    #     if not result:
    #         return
    #
    #     summary = result.get('summary', {})
    #     color_result = result.get('color_result', {})
    #     attr_result = result.get('attributes_result', {})
    #
    #     # 1. 更新颜色显示
    #     if color_result and color_result.get('success'):
    #         color = color_result.get('final_color', '未知')
    #         self.color_label.setText(f"上衣颜色: {color}")
    #         self.color_label.setStyleSheet(
    #             f"font-weight: bold; color: #e74c3c; font-size: 14px;"
    #             f"background-color: #f9f9f9; padding: 5px; border-radius: 3px;"
    #         )
    #
    #     # 2. 更新属性表格
    #     if attr_result and attr_result.get('success'):
    #         probs = attr_result.get('probs', [])
    #         labels = attr_result.get('labels', [])
    #         above_threshold = attr_result.get('above_threshold', [])
    #
    #         self.attributes_table.setRowCount(len(labels))
    #
    #         for i, (label, prob) in enumerate(zip(labels, probs)):
    #             # 属性名（中英文）
    #             chi_label = self.videoThread.attributes_label_map.get(label,
    #                                                                   label) if self.videoThread.attributes_label_map else label
    #
    #             # 概率显示
    #             prob_item = QTableWidgetItem(f"{prob:.1%}")
    #
    #             # 状态标记
    #             is_above = i in above_threshold
    #             status = "✓" if is_above else "✗"
    #             status_item = QTableWidgetItem(status)
    #
    #             if is_above:
    #                 status_item.setForeground(QColor(0, 128, 0))  # 绿色
    #                 prob_item.setForeground(QColor(0, 128, 0))
    #             else:
    #                 status_item.setForeground(QColor(150, 150, 150))  # 灰色
    #                 prob_item.setForeground(QColor(150, 150, 150))
    #
    #             self.attributes_table.setItem(i, 0, QTableWidgetItem(chi_label))
    #             self.attributes_table.setItem(i, 1, prob_item)
    #             self.attributes_table.setItem(i, 2, status_item)

    def send_attributes_to_plc(self, attributes_result):
        """将属性结果发送到PLC（简化版）"""
        if not hasattr(self, 'plcThread') or not self.plcThread or not self.plcThread.isRunning():
            return

        # 确保PLC线程在运行
        if not self.plcThread.isRunning():
            self.printMessage("PLC线程未运行，无法发送属性数据")
            return

        try:
            # 只需调用PLC线程的方法，编码工作由PLC线程完成
            self.plcThread.update_person_attributes(attributes_result)

            # 可选：记录日志
            summary = attributes_result.get('summary', {})
            color = summary.get('color', '未知')
            attrs_count = len(summary.get('main_attributes', []))
            self.printMessage(f"属性数据发送到PLC: 颜色{color}, {attrs_count}个属性")

        except Exception as e:
            self.printMessage(f"发送属性到PLC失败: {e}")
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

    def toggle_attributes_analysis(self):
        """切换属性识别功能开关"""
        current_text = self.attributesButton.text()

        if current_text == "开启属性识别":
            # 执行开启逻辑
            success = self.enable_attributes_analysis()
            if success:
                self.attributesButton.setText("关闭属性识别")
                self.attributesButton.setStyleSheet("background-color: rgb(170, 255, 127);")  # 绿色背景
                self.attributes_enabled = True
                self.printMessage("人物属性识别功能已开启")
                # 显示属性面板（如果已创建）
                if hasattr(self, 'attributes_display'):
                    self.attributes_display.show()
            else:
                self.printMessage("开启属性识别失败，请检查模型配置")
        else:
            # 执行关闭逻辑
            self.disable_attributes_analysis()
            self.attributesButton.setText("开启属性识别")
            self.attributesButton.setStyleSheet("")  # 恢复默认样式
            self.attributes_enabled = False
            self.printMessage("人物属性识别功能已关闭")
            # 可选：清空UI显示
            self._clear_attributes_display()

    def enable_attributes_analysis(self):
        """启用人物属性识别功能"""
        try:
            # 1. 检查模型路径配置
            if not self.setting or 'person_attributes' not in self.setting:
                self.printMessage("未找到属性识别配置，请检查settings.json")
                return False

            config = self.setting['person_attributes']
            model_dir = config.get('model_dir', '')

            if not model_dir:
                self.printMessage("未配置属性识别模型路径")
                return False

            # 2. 转换为绝对路径（如果需要）
            if not os.path.isabs(model_dir):
                # 基于当前工作目录
                abs_model_dir = os.path.join(os.getcwd(), model_dir)
                if not os.path.exists(abs_model_dir):
                    self.printMessage(f"模型路径不存在: {abs_model_dir}")
                    return False
                model_dir = abs_model_dir

            # 3. 配置视频处理线程
            # 设置模型路径
            self.videoThread.set_attributes_model_dir(model_dir)

            # 设置更新间隔（从配置读取或使用默认值）
            update_interval = config.get('update_interval', 15)
            self.videoThread.set_attributes_update_interval(update_interval)

            # 设置阈值（从配置读取或使用默认值）
            threshold = config.get('threshold', 0.65)
            self.printMessage(f"从配置读取阈值: {threshold}")
            self.videoThread.set_attributes_threshold(threshold)

            # 4. 启用属性识别
            self.videoThread.set_attributes_enabled(True)

            # 5. 创建属性显示UI（如果尚未创建）
            if not hasattr(self, 'attributes_display') or self.attributes_display is None:
                self.create_attributes_display()

            return True

        except Exception as e:
            self.printMessage(f"启用属性识别时出错: {str(e)}")
            return False

    def disable_attributes_analysis(self):
        """禁用人物属性识别功能"""
        try:
            # 1. 通知视频处理线程禁用属性识别
            self.videoThread.set_attributes_enabled(False)

            # 2. 清空属性显示
            self.clear_attributes_display()

            # 3. 可选：隐藏属性显示面板（根据你的设计决定）
            # if self.attributes_display:
            #     self.attributes_display.hide()

            return True

        except Exception as e:
            self.printMessage(f"禁用属性识别时出错: {str(e)}")
            return False

    def clear_attributes_display(self):
        """清空属性显示"""
        if hasattr(self, 'color_label') and self.color_label:
            self.color_label.setText("上衣颜色: --")

        if hasattr(self, 'attributes_table') and self.attributes_table:
            self.attributes_table.setRowCount(0)
            self.attributes_table.clearContents()

    def toggle_attributes_panel(self):
        """折叠/展开属性面板"""
        if self.attributes_panel_expanded:
            # 折叠：只显示标题
            self.color_label.hide()
            self.key_attributes_label.hide()
            self.attributes_table.hide()
            self.toggle_attributes_btn.setText("▼")
            self.attributes_display.setMaximumHeight(30)
        else:
            # 展开：显示全部
            self.color_label.show()
            self.key_attributes_label.show()
            self.attributes_table.show()
            self.toggle_attributes_btn.setText("▲")
            self.attributes_display.setMaximumHeight(400)

        self.attributes_panel_expanded = not self.attributes_panel_expanded

    def _clear_attributes_display(self):
        """清空属性显示"""
        if hasattr(self, 'color_label'):
            self.color_label.setText("上衣颜色: --")
        if hasattr(self, 'key_attributes_label'):
            self.key_attributes_label.setText("显著特征: --")
        if hasattr(self, 'attributes_table'):
            self.attributes_table.setRowCount(0)

    def enable_attributes_analysis(self):
        """启用人物属性识别功能（修正版）"""
        try:
            # 1. 检查模型路径配置
            if not self.setting or 'person_attributes' not in self.setting:
                self.printMessage("未找到属性识别配置，请检查settings.json")
                return False

            config = self.setting['person_attributes']
            model_dir = config.get('model_dir', '')

            if not model_dir:
                self.printMessage("未配置属性识别模型路径")
                return False

            # 2. 转换为绝对路径（如果需要）
            if not os.path.isabs(model_dir):
                # 基于当前工作目录
                abs_model_dir = os.path.join(os.getcwd(), model_dir)
                if not os.path.exists(abs_model_dir):
                    self.printMessage(f"模型路径不存在: {abs_model_dir}")
                    return False
                model_dir = abs_model_dir

            # 3. 配置视频处理线程 - 使用正确的方法名
            # 设置模型路径
            self.videoThread.set_attributes_model_dir(model_dir)  # ✅ 现在这个方法存在了

            # 设置更新间隔
            update_interval = config.get('update_interval', 15)
            self.videoThread.set_attributes_update_interval(update_interval)

            # 设置阈值
            threshold = config.get('threshold', 0.65)
            self.videoThread.set_attributes_threshold(threshold)

            # 4. 启用属性识别
            self.videoThread.set_attributes_enabled(True)

            # 5. 创建属性显示UI（如果尚未创建）
            if not hasattr(self, 'attributes_display') or self.attributes_display is None:
                self.create_attributes_display()
            else:
                self.attributes_display.show()

            self.printMessage(f"人物属性识别已启用，模型: {model_dir}")
            return True

        except Exception as e:
            self.printMessage(f"启用属性识别时出错: {str(e)}")
            return False

    def test_attributes_analysis_base(self):
        """测试属性识别功能，单次执行"""
        try:
            self.printMessage("=== 开始属性识别测试 测试成功后此功能删除 ===")

            # 1. 检查属性识别模块是否可用
            if not PERSON_ATTRIBUTES_AVAILABLE:
                self.printMessage("警告: PersonAttributes模块不可用")
                return

            # 2. 获取当前视频帧（直接从摄像头获取）
            if not self.videoThread or not self.videoThread.Cam:
                self.printMessage("错误: 视频线程或摄像头未初始化")
                return

            # 获取一帧图像
            frame = self.videoThread.Cam.get_frame()
            if frame is None:
                self.printMessage("错误: 无法获取视频帧")
                return

            self.printMessage(f"获取帧成功，尺寸: {frame.shape}")

            # 3. 检查模型路径
            if not self.setting or 'person_attributes' not in self.setting:
                self.printMessage("错误: 未找到属性识别配置")
                return

            config = self.setting['person_attributes']
            model_dir = config.get('model_dir', '')

            if not model_dir or not os.path.exists(model_dir):
                self.printMessage(f"错误: 模型路径不存在: {model_dir}")
                return

            self.printMessage(f"模型路径: {model_dir}")

            # 4. 创建独立的属性识别器（使用CPU，避免GPU冲突）
            try:
                from person_attributes import PersonAttributes

                # 使用CPU模式，避免与YOLO模型冲突
                detector = PersonAttributes(
                    model_dir=model_dir,
                    use_gpu=False  # 使用CPU测试
                )
                self.printMessage("属性识别器创建成功（CPU模式）")
            except Exception as e:
                self.printMessage(f"创建属性识别器失败: {str(e)}")
                return

            # 5. 手动选择一个目标区域（测试用，可以选择画面中心区域）
            h, w = frame.shape[:2]
            # 选择画面中心区域作为测试
            center_x, center_y = w // 2, h // 2
            bbox_size = 200
            x1 = max(0, center_x - bbox_size // 2)
            y1 = max(0, center_y - bbox_size // 2)
            x2 = min(w, center_x + bbox_size // 2)
            y2 = min(h, center_y + bbox_size // 2)

            bbox = [x1, y1, x2, y2]
            self.printMessage(f"测试区域: {bbox}")

            # 6. 裁剪目标区域
            person_img = frame[y1:y2, x1:x2]
            if person_img.size == 0:
                self.printMessage("错误: 裁剪区域为空")
                return

            # 保存测试图片（可选，用于调试）
            test_img_path = os.path.join(os.getcwd(), "test_person.jpg")
            cv2.imwrite(test_img_path, person_img)
            self.printMessage(f"保存测试图片到: {test_img_path}")

            # 7. 执行属性识别
            self.printMessage("开始执行属性识别...")
            start_time = time.time()

            try:
                result = detector.analyze_full(
                    person_img,
                    analyze_color=True,
                    analyze_attributes=True
                )

                elapsed_time = time.time() - start_time
                self.printMessage(f"属性识别完成，耗时: {elapsed_time:.2f}秒")

            except Exception as e:
                self.printMessage(f"属性识别执行失败: {str(e)}")
                import traceback
                self.printMessage(f"详细错误: {traceback.format_exc()}")
                return

            # 8. 显示结果
            self.printMessage("=== 属性识别结果 ===")

            # 颜色结果
            color_result = result.get('color_result', {})
            if color_result and color_result.get('success'):
                color = color_result.get('final_color', '未知')
                self.printMessage(f"上衣颜色: {color}")

                # 显示详细投票信息
                votes = color_result.get('votes', [])
                vote_str = ", ".join(votes)
                self.printMessage(f"颜色投票: {vote_str}")

            # 属性结果
            attr_result = result.get('attributes_result', {})
            if attr_result and attr_result.get('success'):
                above_threshold = attr_result.get('above_threshold', [])
                labels = attr_result.get('labels', [])
                probs = attr_result.get('probs', [])

                self.printMessage(f"识别到 {len(above_threshold)} 个超过阈值的属性:")

                for idx in above_threshold:
                    if idx < len(labels):
                        eng_label = labels[idx]
                        chi_label = detector.LABEL_MAP.get(eng_label, eng_label)
                        prob = probs[idx]
                        self.printMessage(f"  - {chi_label}: {prob:.1%}")

            # 摘要信息
            summary = result.get('summary', {})
            color = summary.get('color', '未知')
            main_attrs = summary.get('main_attributes', [])

            if main_attrs:
                attrs_str = "、".join(main_attrs[:3])
                if len(main_attrs) > 3:
                    attrs_str += f" 等{len(main_attrs)}个"
                self.printMessage(f"摘要: 上衣{color}，特征: {attrs_str}")
            else:
                self.printMessage(f"摘要: 上衣{color}，无明显特征")

            # 9. 清理资源
            del detector
            self.printMessage("=== 测试完成 ===")

            # 测试通过后，可以尝试在GPU上运行一次
            self.test_gpu_attribute_detection()

        except Exception as e:
            self.printMessage(f"测试过程中发生异常: {str(e)}")
            import traceback
            self.printMessage(f"详细错误: {traceback.format_exc()}")

    def test_attributes_analysis(self):
        """测试属性识别功能，单次执行"""
        try:
            self.printMessage("=== 开始属性识别测试 ===")

            # 1. 本地检查属性识别模块是否可用
            try:
                from person_attributes import PersonAttributes
                self.printMessage("✓ PersonAttributes模块可以导入")
            except ImportError as e:
                self.printMessage(f"✗ 无法导入PersonAttributes模块: {e}")
                return

            # 2. 获取当前视频帧（直接从摄像头获取）
            if not self.videoThread or not self.videoThread.Cam:
                self.printMessage("错误: 视频线程或摄像头未初始化")
                return

            # 3. 获取一帧图像
            try:
                frame = self.videoThread.Cam.get_frame()
                if frame is None:
                    self.printMessage("错误: 无法获取视频帧")
                    return
                self.printMessage(f"✓ 获取帧成功，尺寸: {frame.shape}")
            except Exception as e:
                self.printMessage(f"获取帧失败: {e}")
                return

            # 4. 检查模型路径
            if not self.setting or 'person_attributes' not in self.setting:
                self.printMessage("错误: 未找到属性识别配置")
                return

            config = self.setting['person_attributes']
            model_dir = config.get('model_dir', '')

            if not model_dir:
                self.printMessage("错误: 未配置模型路径")
                return

            # 转换为绝对路径
            if not os.path.isabs(model_dir):
                model_dir = os.path.abspath(model_dir)

            if not os.path.exists(model_dir):
                self.printMessage(f"错误: 模型路径不存在: {model_dir}")
                return

            self.printMessage(f"✓ 模型路径: {model_dir}")

            # 5. 创建属性识别器（使用CPU）
            try:
                detector = PersonAttributes(
                    model_dir=model_dir,
                    use_gpu=False  # 使用CPU，避免冲突
                )
                self.printMessage("✓ 属性识别器创建成功")
            except Exception as e:
                self.printMessage(f"✗ 创建属性识别器失败: {str(e)}")
                import traceback
                self.printMessage(f"详细错误: {traceback.format_exc()}")
                return

            # 6. 手动选择测试区域（画面中心）
            h, w = frame.shape[:2]
            center_x, center_y = w // 2, h // 2
            bbox_size = min(w, h) // 3  # 选择画面1/3大小的区域

            x1 = max(0, center_x - bbox_size // 2)
            y1 = max(0, center_y - bbox_size // 2)
            x2 = min(w, center_x + bbox_size // 2)
            y2 = min(h, center_y + bbox_size // 2)

            bbox = [x1, y1, x2, y2]
            self.printMessage(f"✓ 测试区域: {bbox}")

            # 7. 裁剪目标区域
            person_img = frame[y1:y2, x1:x2]
            if person_img.size == 0:
                self.printMessage("错误: 裁剪区域为空")
                return

            # 保存测试图片（用于调试）
            test_img_path = os.path.join(os.getcwd(), "test_person.jpg")
            try:
                cv2.imwrite(test_img_path, person_img)
                self.printMessage(f"✓ 保存测试图片到: {test_img_path}")
            except Exception as e:
                self.printMessage(f"警告: 无法保存测试图片: {e}")

            # 8. 执行属性识别
            self.printMessage("开始执行属性识别...")
            start_time = time.time()

            try:
                result = detector.analyze_full(
                    person_img,
                    analyze_color=True,
                    analyze_attributes=True
                )

                elapsed_time = time.time() - start_time
                self.printMessage(f"✓ 属性识别完成，耗时: {elapsed_time:.2f}秒")

            except Exception as e:
                self.printMessage(f"✗ 属性识别执行失败: {str(e)}")
                import traceback
                self.printMessage(f"详细错误: {traceback.format_exc()}")
                return

            # 9. 显示结果
            self.printMessage("=== 属性识别结果 ===")

            # 检查是否有结果
            if not result:
                self.printMessage("✗ 没有返回结果")
                return

            # 颜色结果
            if 'color_result' in result:
                color_result = result['color_result']
                if color_result and color_result.get('success'):
                    color = color_result.get('final_color', '未知')
                    self.printMessage(f"✓ 上衣颜色: {color}")

                    # 显示详细投票信息
                    if 'votes' in color_result:
                        votes = color_result['votes']
                        vote_str = ", ".join(votes)
                        self.printMessage(f"颜色投票: {vote_str}")
                else:
                    self.printMessage(f"颜色识别失败: {color_result.get('error', '未知错误')}")
            else:
                self.printMessage("✗ 结果中没有颜色信息")

            # 属性结果
            if 'attributes_result' in result:
                attr_result = result['attributes_result']
                if attr_result and attr_result.get('success'):
                    above_threshold = attr_result.get('above_threshold', [])
                    labels = attr_result.get('labels', [])
                    probs = attr_result.get('probs', [])

                    self.printMessage(f"✓ 识别到 {len(above_threshold)} 个超过阈值的属性:")

                    for idx in above_threshold[:5]:  # 最多显示5个
                        if idx < len(labels):
                            eng_label = labels[idx]
                            chi_label = detector.LABEL_MAP.get(eng_label, eng_label)
                            prob = probs[idx] if idx < len(probs) else 0
                            self.printMessage(f"  - {chi_label}: {prob:.1%}")

                    if len(above_threshold) > 5:
                        self.printMessage(f"  ... 等{len(above_threshold)}个属性")
                else:
                    self.printMessage(f"属性识别失败: {attr_result.get('error', '未知错误')}")
            else:
                self.printMessage("✗ 结果中没有属性信息")

            # 摘要信息
            if 'summary' in result:
                summary = result['summary']
                color = summary.get('color', '未知')
                main_attrs = summary.get('main_attributes', [])

                if main_attrs:
                    attrs_str = "、".join(main_attrs[:3])
                    if len(main_attrs) > 3:
                        attrs_str += f" 等{len(main_attrs)}个"
                    self.printMessage(f"✓ 摘要: 上衣{color}，特征: {attrs_str}")
                else:
                    self.printMessage(f"✓ 摘要: 上衣{color}，无明显特征")
            else:
                self.printMessage("✗ 结果中没有摘要信息")

            # 10. 清理资源
            del detector
            self.printMessage("=== 测试完成 ===")

            # 11. 测试GPU模式（可选）
            self.test_gpu_attribute_detection(person_img)

        except Exception as e:
            self.printMessage(f"测试过程中发生异常: {str(e)}")
            import traceback
            self.printMessage(f"详细错误: {traceback.format_exc()}")


    def test_gpu_attribute_detection(self, test_image=None):
        """测试GPU模式下的属性识别"""
        try:
            self.printMessage("\n=== 测试GPU模式属性识别 ===")

            # 检查CUDA是否可用
            import torch
            if not torch.cuda.is_available():
                self.printMessage("警告: CUDA不可用，跳过GPU测试")
                return

            self.printMessage(f"GPU设备: {torch.cuda.get_device_name(0)}")

            # 创建GPU模式的检测器
            from person_attributes import PersonAttributes
            config = self.setting['person_attributes']
            model_dir = config.get('model_dir', '')

            # 创建GPU检测器
            detector = PersonAttributes(
                model_dir=model_dir,
                use_gpu=True
            )
            self.printMessage("✓ GPU模式属性识别器创建成功")

            # 准备测试图像
            img_to_test = None

            if test_image is not None:
                img_to_test = test_image
                self.printMessage("✓ 使用传入的测试图像")
            else:
                # 尝试从文件读取
                test_img_path = os.path.join(os.getcwd(), "test_person.jpg")
                if os.path.exists(test_img_path):
                    import cv2
                    img_to_test = cv2.imread(test_img_path)
                    if img_to_test is not None:
                        self.printMessage("✓ 从文件读取测试图像")
                    else:
                        self.printMessage("✗ 无法读取测试图片")
                        return
                else:
                    self.printMessage("✗ 测试图片不存在")
                    return

            if img_to_test is None:
                self.printMessage("✗ 没有可用于测试的图像")
                return

            # 执行GPU模式属性识别
            self.printMessage("开始执行GPU模式属性识别...")
            start_time = time.time()

            try:
                result = detector.analyze_full(
                    img_to_test,
                    analyze_color=True,
                    analyze_attributes=True
                )

                elapsed_time = time.time() - start_time
                self.printMessage(f"✓ GPU模式属性识别完成，耗时: {elapsed_time:.2f}秒")

            except Exception as e:
                self.printMessage(f"✗ GPU模式属性识别执行失败: {str(e)}")
                import traceback
                self.printMessage(f"详细错误: {traceback.format_exc()}")
                return

            # 显示GPU测试结果
            self.printMessage("=== GPU模式属性识别结果 ===")

            # 颜色结果
            if 'color_result' in result:
                color_result = result['color_result']
                if color_result and color_result.get('success'):
                    color = color_result.get('final_color', '未知')
                    self.printMessage(f"✓ 上衣颜色: {color}")

                    # 显示详细投票信息
                    if 'votes' in color_result:
                        votes = color_result['votes']
                        vote_str = ", ".join(votes)
                        self.printMessage(f"颜色投票: {vote_str}")
                else:
                    self.printMessage(f"颜色识别失败: {color_result.get('error', '未知错误')}")
            else:
                self.printMessage("✗ 结果中没有颜色信息")

            # 属性结果
            if 'attributes_result' in result:
                attr_result = result['attributes_result']
                if attr_result and attr_result.get('success'):
                    above_threshold = attr_result.get('above_threshold', [])
                    labels = attr_result.get('labels', [])
                    probs = attr_result.get('probs', [])

                    self.printMessage(f"✓ 识别到 {len(above_threshold)} 个超过阈值的属性:")

                    for idx in above_threshold[:5]:  # 最多显示5个
                        if idx < len(labels):
                            eng_label = labels[idx]
                            chi_label = detector.LABEL_MAP.get(eng_label, eng_label)
                            prob = probs[idx] if idx < len(probs) else 0
                            self.printMessage(f"  - {chi_label}: {prob:.1%}")

                    if len(above_threshold) > 5:
                        self.printMessage(f"  ... 等{len(above_threshold)}个属性")

                    # 显示所有属性的概率（详细对比）
                    self.printMessage("\n=== 详细属性概率对比 ===")
                    self.printMessage("属性              CPU概率  GPU概率  差值")
                    self.printMessage("-------------------------------------")

                    # 为了对比，我们需要获取CPU模式的结果
                    # 这里我们假设CPU测试已经完成，可以重新运行或保存结果
                    # 为了简化，我们只显示GPU结果，CPU结果需要从之前的测试中获取
                    # 这里只显示GPU结果，如果需要对比，可以修改代码保存CPU结果

                else:
                    self.printMessage(f"属性识别失败: {attr_result.get('error', '未知错误')}")
            else:
                self.printMessage("✗ 结果中没有属性信息")

            # 摘要信息
            if 'summary' in result:
                summary = result['summary']
                color = summary.get('color', '未知')
                main_attrs = summary.get('main_attributes', [])

                if main_attrs:
                    attrs_str = "、".join(main_attrs[:3])
                    if len(main_attrs) > 3:
                        attrs_str += f" 等{len(main_attrs)}个"
                    self.printMessage(f"✓ 摘要: 上衣{color}，特征: {attrs_str}")
                else:
                    self.printMessage(f"✓ 摘要: 上衣{color}，无明显特征")
            else:
                self.printMessage("✗ 结果中没有摘要信息")

            # GPU内存使用情况
            try:
                allocated = torch.cuda.memory_allocated() / 1024 ** 3
                cached = torch.cuda.memory_reserved() / 1024 ** 3
                self.printMessage(f"\n=== GPU内存使用 ===")
                self.printMessage(f"已分配内存: {allocated:.2f} GB")
                self.printMessage(f"缓存内存: {cached:.2f} GB")
            except Exception as e:
                self.printMessage(f"获取GPU内存信息失败: {e}")

            # 清理资源
            del detector

            # 清理CUDA缓存
            torch.cuda.empty_cache()

            self.printMessage("=== GPU模式测试完成 ===")

        except Exception as e:
            self.printMessage(f"GPU测试失败: {str(e)}")
            import traceback
            self.printMessage(f"详细错误: {traceback.format_exc()}")

    def set_attributes_cpu_mode(self, state):
        use_cpu = self.cpuModeCheckbox.isChecked()
        self.videoThread.set_attributes_use_cpu(use_cpu)



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