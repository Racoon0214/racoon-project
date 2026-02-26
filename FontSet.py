import sys
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import json
import copy


class FontSettingsDialog(QDialog):
    def __init__(self, parent=None, current_font=QFont(), current_color=QColor(0, 0, 0)):
        super().__init__(parent)
        self.current_font = current_font  # 保存传入的当前字体
        self.preview_text = "This is a preview of the font settings."
        self.current_color = current_color
        self.initUI()

    def initUI(self):
        self.setWindowTitle('字体设置')

        # 字体家族组合框
        self.font_family_combo = QFontComboBox()
        self.font_family_combo.setCurrentFont(self.current_font)  # 设置当前字体

        # 字体大小微调框
        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setValue(self.current_font.pointSize())
        self.font_size_spinbox.setRange(6, 100)
        # self.font_size_spinbox.valueChanged.connect(self.update_preview)

        # 粗体复选框
        self.bold_checkbox = QCheckBox('Bold')
        self.bold_checkbox.setChecked(self.current_font.bold())
        # self.bold_checkbox.stateChanged.connect(self.update_preview)

        # 斜体复选框
        self.italic_checkbox = QCheckBox("Italic", self)
        self.italic_checkbox.setChecked(self.current_font.italic())
        # self.italic_checkbox.stateChanged.connect(self.update_preview)

        # 颜色设置
        self.color_button = QPushButton("选择颜色", self)
        self.color_button.clicked.connect(self.select_color)

        # 预览文本编辑框
        self.preview_text_edit = QTextEdit()
        self.preview_text_edit.setReadOnly(True)
        self.update_preview()  # 初始化预览

        # 布局
        form_layout = QFormLayout()
        form_layout.addRow('Font Family:', self.font_family_combo)
        form_layout.addRow('Font Size:', self.font_size_spinbox)
        form_layout.addRow(self.bold_checkbox, self.italic_checkbox)
        form_layout.addRow(self.color_button)

        layout = QVBoxLayout()
        layout.addLayout(form_layout)
        layout.addWidget(self.preview_text_edit)

        buttons = QHBoxLayout()
        confirm_button = QPushButton('Confirm')
        confirm_button.clicked.connect(self.accept)
        cancel_button = QPushButton('Cancel')
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(confirm_button)
        buttons.addWidget(cancel_button)

        layout.addLayout(buttons)
        self.setLayout(layout)

        # 连接信号和槽
        self.font_family_combo.currentFontChanged.connect(self.update_preview)
        self.font_size_spinbox.valueChanged.connect(self.update_preview)
        self.bold_checkbox.stateChanged.connect(self.update_preview)
        self.italic_checkbox.stateChanged.connect(self.update_preview)

    def select_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.current_color = color
            print(type(color), color)
            self.update_preview()

    def update_preview(self):
        # 根据当前设置更新预览文本
        font = self.font_family_combo.currentFont()
        font.setPointSize(self.font_size_spinbox.value())
        font.setBold(self.bold_checkbox.isChecked())
        font.setItalic(self.italic_checkbox.isChecked())
        self.preview_text_edit.setFont(font)
        # 先设置颜色,再写文字
        self.preview_text_edit.setTextColor(self.current_color)
        self.preview_text_edit.setPlainText(self.preview_text)
        # self.preview_text_edit.setStyleSheet(f"color: rgb({self.current_color.red()}, {self.current_color.green()}, {self.current_color.blue()});")

    def get_selected_font(self):
        # 返回用户选择的字体
        font = self.font_family_combo.currentFont()
        font.setPointSize(self.font_size_spinbox.value())
        font.setBold(self.bold_checkbox.isChecked())
        font.setItalic(self.italic_checkbox.isChecked())
        return font, self.current_color


class FontSettingsWidget(QWidget):
    def __init__(self, parent=None, current_font=QFont(), current_color=QColor(0, 0, 0)):
        super().__init__(parent)
        self.current_font = current_font  # 保存传入的当前字体
        self.preview_text = "This is a preview of the font settings."
        self.current_color = current_color
        self.initUI()

    def initUI(self):
        self.setWindowTitle('字体设置')

        # 字体家族组合框
        self.font_family_combo = QFontComboBox()
        self.font_family_combo.setCurrentFont(self.current_font)  # 设置当前字体

        # 字体大小微调框
        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setValue(self.current_font.pointSize())
        self.font_size_spinbox.setRange(6, 100)
        # self.font_size_spinbox.valueChanged.connect(self.update_preview)

        # 粗体复选框
        self.bold_checkbox = QCheckBox('Bold')
        self.bold_checkbox.setChecked(self.current_font.bold())
        # self.bold_checkbox.stateChanged.connect(self.update_preview)

        # 斜体复选框
        self.italic_checkbox = QCheckBox("Italic", self)
        self.italic_checkbox.setChecked(self.current_font.italic())
        # self.italic_checkbox.stateChanged.connect(self.update_preview)

        # 颜色设置
        self.color_button = QPushButton("选择颜色", self)
        self.color_button.clicked.connect(self.select_color)

        # 预览文本编辑框
        self.preview_text_edit = QTextEdit()
        self.preview_text_edit.setReadOnly(True)
        self.update_preview()  # 初始化预览

        # 布局
        form_layout = QFormLayout()
        form_layout.addRow('Font Family:', self.font_family_combo)
        form_layout.addRow('Font Size:', self.font_size_spinbox)
        form_layout.addRow(self.bold_checkbox, self.italic_checkbox)
        form_layout.addRow(self.color_button)

        layout = QVBoxLayout()
        layout.addLayout(form_layout)
        layout.addWidget(self.preview_text_edit)

        # buttons = QHBoxLayout()
        # confirm_button = QPushButton('Confirm')
        # confirm_button.clicked.connect(self.accept)
        # cancel_button = QPushButton('Cancel')
        # cancel_button.clicked.connect(self.reject)
        # buttons.addWidget(confirm_button)
        # buttons.addWidget(cancel_button)

        # layout.addLayout(buttons)
        self.setLayout(layout)

        # 连接信号和槽
        self.font_family_combo.currentFontChanged.connect(self.update_preview)
        self.font_size_spinbox.valueChanged.connect(self.update_preview)
        self.bold_checkbox.stateChanged.connect(self.update_preview)
        self.italic_checkbox.stateChanged.connect(self.update_preview)

    def select_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.current_color = color
            print(type(color), color)
            self.update_preview()

    def update_preview(self):
        # 根据当前设置更新预览文本
        font = self.font_family_combo.currentFont()
        font.setPointSize(self.font_size_spinbox.value())
        font.setBold(self.bold_checkbox.isChecked())
        font.setItalic(self.italic_checkbox.isChecked())
        self.preview_text_edit.setFont(font)
        # 先设置颜色,再写文字
        self.preview_text_edit.setTextColor(self.current_color)
        self.preview_text_edit.setPlainText(self.preview_text)
        # self.preview_text_edit.setStyleSheet(f"color: rgb({self.current_color.red()}, {self.current_color.green()}, {self.current_color.blue()});")

    def get_selected_font(self):
        # 返回用户选择的字体
        font = self.font_family_combo.currentFont()
        font.setPointSize(self.font_size_spinbox.value())
        font.setBold(self.bold_checkbox.isChecked())
        font.setItalic(self.italic_checkbox.isChecked())
        return font, self.current_color


class Setting(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        # self.initUI()

    def initUI(self, output_font, output_color, voice_font, voice_color, setting):
        if setting is None:
            raise ValueError("输入setting为空")
        self.setting = setting
        self.mainLayout = QVBoxLayout(self)
        self.tabWidget = QTabWidget()

        # 输出字体设置
        self.outputSettingsTab = FontSettingsWidget(self, output_font, output_color)
        # self.visualSettingsTab.setLayout(self.visualSettingsLayout)
        self.tabWidget.addTab(self.outputSettingsTab, "输出字体设置")

        # 字幕字体设置
        self.subtitleSettingsTab = FontSettingsWidget(self, voice_font, voice_color)
        # self.visualSettingsTab.setLayout(self.visualSettingsLayout)
        self.tabWidget.addTab(self.subtitleSettingsTab, "字幕字体设置")

        # 视觉参数设置
        self.visualSettingsTab = QTabWidget()
        self.visualSettingsLayout = QVBoxLayout()
        # 添加描述词和参数控件到基本设置标签页
        self.acc_thre = QLineEdit(self)
        self.addParameter(self.visualSettingsLayout, "动作识别阈值（0.0-1.0，默认0.6）", self.acc_thre)
        self.acc_thre.textChanged.connect(self.checkParam2)

        self.target_id = QLineEdit(self)
        self.addParameter(self.visualSettingsLayout, "视觉启动时默认跟踪ID（默认取值0）", self.target_id)
        self.target_id.textChanged.connect(self.checkParam)

        self.detectFalseCount_thre = QLineEdit(self)
        self.addParameter(self.visualSettingsLayout, "检测匹配发送间隔（默认取值30）", self.detectFalseCount_thre)
        self.detectFalseCount_thre.textChanged.connect(self.checkParam)
        self.detectFalseCount_thre_time = QLineEdit(self)
        self.addParameter(self.visualSettingsLayout, "未检测重置匹配ID时间（默认取值10）",
                          self.detectFalseCount_thre_time)
        self.detectFalseCount_thre_time.textChanged.connect(self.checkParam)

        self.image_match_thre = QLineEdit(self)
        self.addParameter(self.visualSettingsLayout, "图像未匹配发送间隔（默认取值10）", self.image_match_thre)
        self.image_match_thre.textChanged.connect(self.checkParam)
        self.image_match_thre_time = QLineEdit(self)
        self.addParameter(self.visualSettingsLayout, "图像未匹配重置ID时间（默认取值5）", self.image_match_thre_time)
        self.image_match_thre_time.textChanged.connect(self.checkParam)

        self.person_lost_thre = QLineEdit(self)
        self.addParameter(self.visualSettingsLayout, "目标ID跟踪失败发送间隔（默认取值20）", self.person_lost_thre)
        self.person_lost_thre.textChanged.connect(self.checkParam)
        self.person_lost_thre_time = QLineEdit(self)
        self.addParameter(self.visualSettingsLayout, "目标ID跟踪失败重置ID时间（默认取值5）", self.person_lost_thre_time)
        self.person_lost_thre_time.textChanged.connect(self.checkParam)

        # 标签页
        self.visualSettingsTab.setLayout(self.visualSettingsLayout)
        self.tabWidget.addTab(self.visualSettingsTab, "视觉参数设置")

        # 文本参数设置
        # self.voiceSettingsTab = QTabWidget()
        # self.voiceSettingsLayout = QVBoxLayout()
        # self.voiceSettingsLayout.setAlignment(Qt.AlignTop)
        # # 添加描述词和参数控件到基本设置标签页
        # self.BeiBei_text_count_thread = QLineEdit(self)
        # self.addParameter(self.voiceSettingsLayout, "字幕显示时间，参考每秒图像显示多少帧（默认值16）：", self.BeiBei_text_count_thread)
        # self.BeiBei_text_count_thread.textChanged.connect(self.checkParam)
        # self.speed = QLineEdit(self)
        # self.addParameter(self.voiceSettingsLayout, "摄像头运动速度（默认值5，范围1-7）：", self.speed)
        # self.speed.textChanged.connect(self.checkParam4)
        # self.sleeptime = QLineEdit(self)
        # self.addParameter(self.voiceSettingsLayout, "摄像头每次运动时间，单位秒（默认值1.0）：", self.sleeptime)
        # self.sleeptime.textChanged.connect(self.checkParam3)
        # self.plc_ip = QLineEdit(self)
        # self.addParameter(self.voiceSettingsLayout, "PLC IP地址：", self.plc_ip)
        # self.plc_port = QLineEdit(self)
        # self.addParameter(self.voiceSettingsLayout, "PLC端口：", self.plc_port)
        # # 标签页设置
        # self.voiceSettingsTab.setLayout(self.voiceSettingsLayout)
        # # self.voiceSettingsLayout.addLayout
        # self.tabWidget.addTab(self.voiceSettingsTab, "语音及其他参数设置")

        # ========== 新增：人物属性识别设置标签页 ==========
        self.personAttributesTab = QWidget()
        self.personAttributesLayout = QVBoxLayout()

        # 启用/禁用属性识别
        self.attributes_enabled = QCheckBox("启用人物属性识别功能", self)
        self.attributes_enabled.setChecked(self.setting.get("person_attributes", {}).get("enabled", False))
        self.personAttributesLayout.addWidget(self.attributes_enabled)

        # 模型目录设置
        self.model_dir = QLineEdit(self)
        self.addParameter(self.personAttributesLayout, "模型目录路径（相对于项目根目录）", self.model_dir)

        # 模型目录浏览按钮
        self.browse_model_btn = QPushButton("浏览模型目录...", self)
        self.browse_model_btn.clicked.connect(self.browse_model_dir)
        self.personAttributesLayout.addWidget(self.browse_model_btn)

        # 更新间隔
        self.update_interval = QLineEdit(self)
        self.addParameter(self.personAttributesLayout, "更新间隔（帧数，默认150）", self.update_interval)
        self.update_interval.textChanged.connect(self.checkParam)

        # 识别阈值
        self.threshold = QLineEdit(self)
        self.addParameter(self.personAttributesLayout, "识别阈值（0.1-0.99，默认0.7）", self.threshold)
        self.threshold.textChanged.connect(self.checkParam2)

        # 显示设置组
        display_group = QGroupBox("显示设置")
        display_layout = QVBoxLayout()

        display_config = self.setting.get("person_attributes", {}).get("display", {})

        self.show_color_patch = QCheckBox("显示颜色块", self)
        self.show_color_patch.setChecked(display_config.get("show_color_patch", True))
        display_layout.addWidget(self.show_color_patch)

        self.max_key_attributes = QLineEdit(self)
        self.addParameterToLayout(display_layout, "最大关键属性数（默认3）", self.max_key_attributes)
        self.max_key_attributes.textChanged.connect(self.checkParam)

        self.auto_collapse = QCheckBox("自动折叠属性面板", self)
        self.auto_collapse.setChecked(display_config.get("auto_collapse", True))
        display_layout.addWidget(self.auto_collapse)

        display_group.setLayout(display_layout)
        self.personAttributesLayout.addWidget(display_group)

        self.personAttributesLayout.addStretch()
        self.personAttributesTab.setLayout(self.personAttributesLayout)
        self.tabWidget.addTab(self.personAttributesTab, "人物属性识别设置")
        # ========== 新增结束 ==========

        # 确认按钮
        buttons = QHBoxLayout()
        confirm_button = QPushButton('确认')
        # 点击confirm后启动数值检查
        confirm_button.clicked.connect(self.accept)
        cancel_button = QPushButton('取消')
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(confirm_button)
        buttons.addWidget(cancel_button)

        # 参数载入并显示
        self.initSet()

        # 页面配置
        # layout.mainLayout(buttons)
        self.mainLayout.addWidget(self.tabWidget)
        self.mainLayout.addLayout(buttons)
        # self.setWindowFlags(Qt.FramelessWindowHint)
        self.setWindowTitle("参数设置")
        self.resize(700, 600)

    def saveSet(self):
        # 字体保存由主函数传入，配置文件的读取和写入都由主函数完成
        # 安全检查在输入时已经检查
        self.setting["visual"]["acc_thre"] = float(self.acc_thre.text())
        self.setting["visual"]["target_id"] = int(self.target_id.text())
        self.setting["visual"]["detectFalseCount_thre"] = int(self.detectFalseCount_thre.text())
        self.setting["visual"]["detectFalseCount_thre_time"] = int(self.detectFalseCount_thre_time.text())
        self.setting["visual"]["image_match_thre"] = int(self.image_match_thre.text())
        self.setting["visual"]["image_match_thre_time"] = int(self.image_match_thre_time.text())
        self.setting["visual"]["person_lost_thre"] = int(self.person_lost_thre.text())
        self.setting["visual"]["person_lost_thre_time"] = int(self.person_lost_thre_time.text())

        # 注释掉语音相关参数保存
        # self.setting["voice"]["BeiBei_text_count_thread"] = int(self.BeiBei_text_count_thread.text())
        # self.setting["camera"]["speed"] = int(self.speed.text())
        # self.setting["camera"]["sleeptime"] = float(self.sleeptime.text())
        # self.setting["voice"]["plc"] = {
        #     "ip": self.plc_ip.text(),
        #     "port": int(self.plc_port.text())
        # }
        # ========== 新增：保存人物属性识别设置 ==========
        person_attributes_config = {
            "enabled": self.attributes_enabled.isChecked(),
            "model_dir": self.model_dir.text(),
            "update_interval": int(self.update_interval.text()) if self.update_interval.text() else 150,
            "threshold": float(self.threshold.text()) if self.threshold.text() else 0.7,
            "display": {
                "show_color_patch": self.show_color_patch.isChecked(),
                "max_key_attributes": int(self.max_key_attributes.text()) if self.max_key_attributes.text() else 3,
                "auto_collapse": self.auto_collapse.isChecked()
            }
        }
        self.setting["person_attributes"] = person_attributes_config
        # ========== 新增结束 ==========

        return self.setting

    def initSet(self):
        self.setting_str = copy.deepcopy(self.setting)
        self.setting_str["visual"] = self.convert_numeric_values_to_strings(self.setting["visual"])

        # 人物属性识别设置初始化
        if "person_attributes" in self.setting:
            person_attrs = self.setting["person_attributes"]
            self.setting_str["person_attributes"] = self.convert_numeric_values_to_strings(person_attrs)

            # 设置UI控件值
            self.attributes_enabled.setChecked(person_attrs.get("enabled", False))
            self.model_dir.setText(person_attrs.get("model_dir", "best_model"))
            self.update_interval.setText(str(person_attrs.get("update_interval", 150)))
            self.threshold.setText(str(person_attrs.get("threshold", 0.7)))

            # 显示设置
            display_config = person_attrs.get("display", {})
            self.show_color_patch.setChecked(display_config.get("show_color_patch", True))
            self.max_key_attributes.setText(str(display_config.get("max_key_attributes", 3)))
            self.auto_collapse.setChecked(display_config.get("auto_collapse", True))

        # 注释掉语音相关参数初始化
        # self.setting_str["voice"] = self.convert_numeric_values_to_strings(self.setting["voice"])
        # self.setting_str["camera"] = self.convert_numeric_values_to_strings(self.setting["camera"])
        # print(type(self.setting))
        self.acc_thre.setText(self.setting_str["visual"]["acc_thre"])
        self.target_id.setText(self.setting_str["visual"]["target_id"])
        self.detectFalseCount_thre.setText(self.setting_str["visual"]["detectFalseCount_thre"])
        self.detectFalseCount_thre_time.setText(self.setting_str["visual"]["detectFalseCount_thre_time"])
        self.image_match_thre.setText(self.setting_str["visual"]["image_match_thre"])
        self.image_match_thre_time.setText(self.setting_str["visual"]["image_match_thre_time"])
        self.person_lost_thre.setText(self.setting_str["visual"]["person_lost_thre"])
        self.person_lost_thre_time.setText(self.setting_str["visual"]["person_lost_thre_time"])

        # 注释掉语音相关参数初始化
        # self.BeiBei_text_count_thread.setText(self.setting_str["voice"]["BeiBei_text_count_thread"])
        # self.speed.setText(self.setting_str["camera"]["speed"])
        # self.sleeptime.setText(self.setting_str["camera"]["sleeptime"])
        # # 初始化PLC参数
        # self.plc_ip.setText(self.setting_str["voice"]["plc"]["ip"])
        # self.plc_port.setText(str(self.setting_str["voice"]["plc"]["port"]))

    def convert_numeric_values_to_strings(self, data):
        """
        递归地将字典中的所有数值转换为字符串。

        :param data: 输入的嵌套字典，其中最终的值都是数值。
        :return: 一个新的字典，其中所有的数值都被转换成了字符串。
        """
        if isinstance(data, dict):
            # 如果数据是字典，递归地转换每个值
            return {key: self.convert_numeric_values_to_strings(value) for key, value in data.items()}
        elif isinstance(data, list):
            # 如果数据是列表，递归地转换每个元素
            return [self.convert_numeric_values_to_strings(element) for element in data]
        elif isinstance(data, (int, float)):
            # 如果数据是数值，将其转换为字符串
            return str(data)
        else:
            # 如果数据不是字典、列表或数值，直接返回（可能是字符串、布尔值等）
            return data

    def setText(self, textEdit, num):
        textEdit.setText(str(num))

    def is_float_string(self, s):
        try:
            value = float(s)
            return value, True
        except ValueError:
            return None, False

    def is_integer_string(self, s):
        try:
            value = int(s)
            return value, True
        except ValueError:
            return None, False

    def checkParam(self, text):
        value, flag = self.is_integer_string(text)
        if flag == False:
            print(value)
            QMessageBox.warning(self, '警告', '输入不是一个有效的整数！')

    def checkParam2(self, text):
        value, flag = self.is_float_string(text)
        # 应该先报格式错误，这两个if语句只会中一个，不会两个都中
        if flag == False:
            QMessageBox.warning(self, '警告', '输入格式错误！')
            return
        if not (0.0 <= value <= 1.0):
            QMessageBox.warning(self, '警告', '输入不在范围内！')

    def checkParam3(self, text):
        value, flag = self.is_float_string(text)
        if flag == False:
            print(value)
            QMessageBox.warning(self, '警告', '输入不是一个有效的整数！')

    def checkParam4(self, text):
        value, flag = self.is_integer_string(text)
        if flag == False:
            QMessageBox.warning(self, '警告', '输入格式错误！')
            return
        if not (1 <= value <= 7):
            QMessageBox.warning(self, '警告', '输入不在范围内！')

    def closeEvent(self, event):
        reply = QMessageBox.question(self, '警告', "是否保存当前改动?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.accept()
            # self.checkParam()
            event.accept()
        else:
            event.ignore()
        return super().closeEvent(event)

    def addParameter(self, layout, labelText, widget):
        """
        在布局中添加一个参数，上方有描述词。
        """
        label = QLabel(labelText, self)
        # 增加一个布局
        Lay = QVBoxLayout()
        Lay.addWidget(label)
        Lay.addWidget(widget)
        layout.addLayout(Lay)

    def browse_model_dir(self):
        """浏览并选择模型目录"""
        from PyQt5.QtWidgets import QFileDialog
        import os

        current_dir = os.getcwd()
        model_dir = self.model_dir.text()

        # 如果当前有模型路径，则以此为起点
        if model_dir and os.path.exists(model_dir):
            if not os.path.isabs(model_dir):
                model_dir = os.path.join(current_dir, model_dir)
        else:
            model_dir = current_dir

        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择属性识别模型目录",
            model_dir,
            QFileDialog.ShowDirsOnly
        )

        if dir_path:
            # 将路径转换为相对路径（相对于当前工作目录）
            try:
                rel_path = os.path.relpath(dir_path, current_dir)
                self.model_dir.setText(rel_path)
            except ValueError:
                # 如果无法转换为相对路径，使用绝对路径
                self.model_dir.setText(dir_path)

    def addParameterToLayout(self, layout, labelText, widget):
        """
        在指定布局中添加一个参数，上方有描述词。
        这是为了在groupbox等内部布局中使用
        """
        label = QLabel(labelText, self)
        param_layout = QVBoxLayout()
        param_layout.addWidget(label)
        param_layout.addWidget(widget)
        layout.addLayout(param_layout)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Main Window')

        # 创建 QTextBrowser 用于显示文本
        self.text_browser = QTextBrowser(self)
        self.default_font = QFont('Arial', 12)  # 设置默认字体
        self.text_browser.setFont(self.default_font)
        self.text_browser.setTextColor(QColor(0, 0, 255))
        self.text_browser.setPlainText("This is the main text browser where the font will be applied.")
        # 创建按钮用于打开字体设置对话框
        self.settings_button = QPushButton('Set Font', self)
        self.settings_button.clicked.connect(self.open_font_settings_dialog)

        # 布局
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.addWidget(self.text_browser)
        layout.addWidget(self.settings_button)

        self.setCentralWidget(central_widget)
        # self.current_color = None

    def open_font_settings_dialog(self):
        # 打开字体设置对话框，并传入当前字体
        dialog = Setting()
        # 注释掉语音字体参数
        dialog.initUI(self.text_browser.font(), self.text_browser.textColor(),
                      self.text_browser.font(), self.text_browser.textColor(), {})
        # dialog.page1 = FontSettingsDialog(self, self.text_browser.font(), self.text_browser.textColor())
        # # dialog.page1.initUI()
        # dialog.page2 = FontSettingsDialog(self, self.text_browser.font(), self.text_browser.textColor())
        # # dialog.page2.initUI()
        if dialog.exec_() == QDialog.Accepted:
            # 获取用户选择的字体并应用到 QTextBrowser
            selected_font, color = dialog.outputSettingsTab.get_selected_font()
            self.text_browser.setFont(selected_font)
            # self.text_browser.setStyleSheet(f"color: rgb({color.red()}, {color.green()}, {color.blue()});")
            self.text_browser.setTextColor(color)
            dialog.saveSet()
            print(f"color: rgb({color.red()}, {color.green()}, {color.blue()});")
            print(
                f"color: rgb({self.text_browser.textColor().red()}, {self.text_browser.textColor().green()}, {self.text_browser.textColor().blue()});")
            self.text_browser.append("hello world")


class FontSetting(QDialog):
    def __init__(self):
        super().__init__()
        self.initUI()
        # self.showMessage = QMessageBox.question()

    def initUI(self, output_font, output_color, voice_font, voice_color, other_setting):
        # 创建顶部栏
        self.toolbar = QToolBar("Top Toolbar")
        self.addToolBar(self.toolbar)

        # 创建两个动作，分别对应两个页面
        self.page1Action = QAction("输出字体设置", self)
        self.page2Action = QAction("字幕字体设置", self)

        # 将动作添加到顶部栏
        self.toolbar.addAction(self.page1Action)
        self.toolbar.addAction(self.page2Action)

        # 连接动作的信号到槽函数
        self.page1Action.triggered.connect(self.showPage1)
        self.page2Action.triggered.connect(self.showPage2)

        # 创建堆叠窗口小部件来容纳不同的页面
        self.stackedWidget = QStackedWidget(self)
        self.setCentralWidget(self.stackedWidget)

        # 创建两个页面小部件并添加到堆叠窗口小部件中
        self.page1 = FontSettingsDialog()
        self.page2 = FontSettingsDialog()
        self.stackedWidget.addWidget(self.page1)
        self.stackedWidget.addWidget(self.page2)

        # 初始显示页面 1
        self.showPage1()

        # 设置窗口标题和大小
        self.setWindowTitle("字体设置页面切换示例")
        self.setGeometry(250, 250, 600, 400)

    def showPage1(self):
        self.stackedWidget.setCurrentIndex(0)

    def showPage2(self):
        self.stackedWidget.setCurrentIndex(1)

    def closeEvent(self, event):
        print("this is closeEvent")

        reply = QMessageBox.question(self, '警告', "系统将退出，是否确认?", QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.No)
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())