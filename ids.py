# 用于
# from PyQt5.QtGui import *
# from PyQt5.QtGui import *
# from PyQt5.QtWidgets import *
# 多次图像匹配功能，目前图像匹配只能执行一次，如果一次没有匹配到就弹出了
from PyQt5.QtCore import *

class IDS(QThread):
    def __init__(self):
        super().__init__(self)
        self.running = True
        self.ids = []

    def run(self):
        while self.running:
            print()
        return super().run()