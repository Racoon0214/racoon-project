from PyQt5.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
from PyQt5.QtGui import QImage, QPixmap, QPainter, QFont, QColor
from PyQt5.QtCore import QTimer, Qt, QRect, QSize
import sys
import cv2
import os
import numpy as np

# 浮动字幕的实现

class ViusalPage(QWidget):
    """不套Qlabel，直接在Qwidet中画图"""
    def __init__(self):
        super().__init__()
        # 设置窗口标题
        self.setWindowTitle("Polar Bear")

        # 设置窗口大小
        self.setGeometry(100, 100, 1285, 726)

        # 设置图片显示
        self.BeiBei_text = None
        self.text = None
        self.frame = np.random.randint(0, 256, (720, 1280, 3), dtype=np.uint8)

        # 字体设置
        # self.initFont()
    
    def initFont(self):
        self.chinese_font = QFont("SimHei", 24)
        self.color = QColor(255, 255, 255)

    def paintEvent(self, event):
        self.frame = cv2.resize(self.frame, (self.width(), self.height()))
        height, width, channel = self.frame.shape
        bytes_per_line = 3 * width
        qimg = QImage(self.frame.data, self.frame.shape[1], self.frame.shape[0], bytes_per_line, QImage.Format_BGR888)
        pixmap = QPixmap.fromImage(qimg)
        if pixmap is not None and self.text is not None:
            painter = QPainter(self)
            painter.drawPixmap(0, 0, pixmap)
            painter.setFont(self.chinese_font)
            painter.setPen(self.color)  # 白色字幕
            text_rect = painter.boundingRect(QRect(0, 0, pixmap.width(), pixmap.height()), Qt.AlignBottom | Qt.AlignCenter, self.text)
            painter.drawText(pixmap.width() // 2 - text_rect.width() // 2, pixmap.height() - text_rect.height() - 25, self.text)
            
        else:
            # print("None", self.text)
            painter = QPainter(self)
            painter.drawPixmap(0, 0, pixmap)

    def setFont(self, font, color):
        if font != None and color != None:
            self.chinese_font = font
            self.color = color

if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = ViusalPage()
    player.show()
    sys.exit(app.exec_())
