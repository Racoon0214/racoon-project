import sys
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, pyqtSlot
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import QGraphicsDropShadowEffect
import json

# 2025.3.21
# 浮动字幕的实现

class FloatingCaption(QWidget):

    def __init__(self, text="浮动字幕初始化完成"):
        super().__init__()
        self.init_settings()  # 初始化设置
        self.initUI(text)
        self.dragging = False
        self.drag_start_position = None
        self.is_enabled = True  # 初始状态为启用
        # self.timer = QTimer(self)
        # self.timer.timeout.connect(self.check_enable_state)
        # self.timer.start(500)  # 每100毫秒检查一次启用状态

    def init_settings(self):
        """从 settings.json 文件中读取字幕设置"""
        try:
            with open("configs\\settings.json", "r", encoding='utf-8') as file:
                self.settings = json.load(file)
        except FileNotFoundError:
            self.settings = {
                "subtitleFont": {
                    "font": "Arial",
                    "size": 26,
                    "italic": False,
                    "bold": False,
                    "color": {
                        "R": 255,
                        "G": 255,
                        "B": 255
                    }
                }
            }
            print("settings.json 文件未找到，使用默认设置。")
        except json.JSONDecodeError:
            self.settings = {
                "subtitleFont": {
                    "font": "Arial",
                    "size": 26,
                    "italic": False,
                    "bold": False,
                    "color": {
                        "R": 255,
                        "G": 255,
                        "B": 255
                    }
                }
            }
            print("settings.json 文件格式错误，使用默认设置。")

    def initUI(self, text):
        self.setWindowTitle('浮动字幕')
        self.setGeometry(100, 100, 400, 100)

        # 设置窗口透明度
        self.setWindowOpacity(0.8)

        # 设置窗口无边框
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)

        # 设置透明背景
        self.setAttribute(Qt.WA_TranslucentBackground)

        layout = QVBoxLayout()

        # 创建字幕标签
        self.caption_label = QLabel(text, self)
        self.caption_label.setAlignment(Qt.AlignCenter)
        font = QFont(self.settings["subtitleFont"]["font"], self.settings["subtitleFont"]["size"])
        font.setItalic(self.settings["subtitleFont"]["italic"])
        font.setBold(self.settings["subtitleFont"]["bold"])
        self.caption_label.setFont(font)
        color = QColor(self.settings["subtitleFont"]["color"]["R"], self.settings["subtitleFont"]["color"]["G"],
                       self.settings["subtitleFont"]["color"]["B"])
        self.caption_label.setStyleSheet(f"color: rgb({color.red()}, {color.green()}, {color.blue()});")

        # 设置文字边框效果
        if(1):
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(8)
            shadow.setColor(QColor(0, 0, 0))  # 白色边框
            shadow.setOffset(0, 0)  # 阴影偏移为0，确保边框在文字四周
            self.caption_label.setGraphicsEffect(shadow)

        layout.addWidget(self.caption_label)
        self.setLayout(layout)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_start_position = event.globalPos() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.move(event.globalPos() - self.drag_start_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = False
            event.accept()

    def update_text(self, new_text):
        if self.is_enabled:
            self.caption_label.setText(new_text)
        else:
            self.caption_label.setText("---")

    @pyqtSlot(bool)
    def change_text_running(self, running):
        self.is_enabled = running

    def set_position(self, position):
        if self.is_enabled:
            screen_geometry = QApplication.primaryScreen().geometry()
            screen_width = screen_geometry.width()
            screen_height = screen_geometry.height()

            if position == "center":
                x = (screen_width - self.width()) // 2
                y = (screen_height - self.height()) // 2
            elif position == "bottom_third":
                x = (screen_width - self.width()) // 2
                y = (screen_height * 3 // 4) - (self.height() // 2)
            elif position == "top_third":
                x = (screen_width - self.width()) // 2
                y = (screen_height // 4) - (self.height() // 2)
            else:
                x, y = 100, 100  # 默认位置

            self.move(x, y)

    def set_size(self, width, height):
        if self.is_enabled:
            self.resize(width, height)

    # def check_enable_state(self):
    #     if not self.is_enabled and self.isVisible():
    #         self.hide()
    #     elif self.is_enabled and not self.isVisible():
    #         self.show()


if __name__ == '__main__':
    app = QApplication(sys.argv)

    caption = FloatingCaption()
    caption.set_size(400, 100)
    caption.set_position("center")  # 设置首次出现的位置为屏幕中间
    caption.show()

    # 更新字幕，可以在你的程序中调用caption.update_text("新的字幕")
    caption.update_text("大家好啊我是说的道理")


    sys.exit(app.exec_())
