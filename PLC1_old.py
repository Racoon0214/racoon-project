from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
# import json
import socket
import time
import pyads
from sqlalchemy import false


class plc_thread(QThread):
    send_to_txt_browser = pyqtSignal(str)
    # plcthread_state = pyqtSignal(bool)
    def __init__(self, ip, port):
        super().__init__()
        self.testItem = 1 #测试
        self.running = True
        self.ip = ip
        self.port = port
        self.voice_plc_data = (1000, "invalid", 100)
        self.visual_plc_data = ("invalid_action", 1000, 1000)
        # 新增锁定状态
        self.vision_lock = 0  # 0表示未锁定，1表示锁定
        # 新增晃动检测相关参数
        self.x_history = []  # 存储最近一段时间内的intdiff_x值
        self.max_history_size = 20  # 存储最近30个数据点（假设每秒1次，即30秒）
        self.swing_threshold = 5  # 方向变化阈值，超过此值认为在晃动
        self.min_movement_threshold = 30  # 最小移动量，小于此值视为抖动而非移动
        self.is_swinging = False  # 当前是否在晃动
        self.swing_count = 0  # 方向变化次数计数器
        self.last_direction = 0  # 上一次移动方向：-1左，0静止，1右
        # 不知道能不能发送空字符串，算了，交给plc的人干吧，空字符串就是没动作；另外，如果画面无人，无人对话，就会发送上一时刻的量，可能会出现，没人也一直发送同一个偏移量和动作过去。。。。。
        self.plc_socket = None
        self.previous_visual_plc_data = None
        self.previous_voice_plc_data = None
        self.connected = False
        # 新增：存储检测到的人体数量
        self.person_count = 0
        # self.startrun = False

        self.action_label_map ={'0': 'cheer_up', '1': 'hand_waving', '2':'jump_up', '3': 'phone_call', '4': 'pick_up','5':'play_with _phone',
                                 '6':'sit_down', '7': 'squat_down', '8':'stand', '9':'taking_a_selfie', '10':'walk'}

    def run(self):
        plc = pyads.Connection('5.157.109.58.1.1', 851)
        retry_count = 0
        max_retries = 5
        retry_delay = 1  # 重试间隔时间（秒）

        # 连接重试循环
        while self.running and retry_count < max_retries:
            if not self.connected:
                try:
                    # 关闭旧连接
                    if plc:
                        plc.close()

                    # 尝试打开连接
                    plc.open()

                    # 验证连接状态
                    if plc.is_open:
                        self.connected = True
                        retry_count = 0  # 重置重试计数器
                        # self.connection_state_changed.emit(True)
                        self.send_to_txt_browser.emit(f"成功连接到PLC!")
                        break
                    else:
                        raise Exception("连接已打开但状态异常")

                except Exception as e:
                    error_msg = f"连接失败 ({retry_count}/{max_retries}): {str(e)}"
                    self.send_to_txt_browser.emit(error_msg)
                    self.connected = False
                    retry_count += 1

                    if retry_count >= max_retries:
                        self.send_to_txt_browser.emit("尝试连接PLC最大次数到达, 中断线程")
                        self.connection_state_changed.emit(False)
                        break

                    time.sleep(retry_delay)

        # if not self.connected:
        #     self.running = False
        #     return

        while self.running:
            label = next((num for num, action in self.action_label_map.items() if action == self.visual_plc_data[0]),
                         None)
            if label is None or label == "":
                label = 0

            try:
                diff_x = int(self.visual_plc_data[1])
            except ValueError:
                diff_x = 0
            try:
                diff_y = int(self.visual_plc_data[2])
            except ValueError:
                diff_y = 0

            intdiff_x = int(((diff_x+450)/900)*100)
            intdiff_y = int(((diff_y + 400) / 800) * 100)
            intdiff_y = 100 - intdiff_y

            # 在重新计算x轴之前判定是否晃动
            # 只在锁定状态下检测晃动
            swinging = false
            if self.vision_lock == 1:
                # 检测是否在左右晃动
                swinging = self.update_swing_detection(intdiff_x)
            else:
                # 未锁定时重置晃动检测
                self.x_history = []
                self.swing_count = 0
                self.last_direction = 0
                if self.is_swinging:
                    self.is_swinging = False
                    self.send_to_txt_browser.emit("目标未锁定，重置晃动检测")

            #     根据不同地点偏移量的设定进行修改。
            # 在发送数据前进行变换
            intxMin = 40
            intxMax = 80

            if intxMin <= intdiff_x <= intxMax:
                intdiff_x = int((intdiff_x - intxMin) * (100 / (intxMax - intxMin)))
            elif intdiff_x < intxMin:
                intdiff_x = 0
            else:
                intdiff_x = 100

            # 确保值在0-100范围内
            # if intdiff_x >100 :
            #     intdiff_x =100
            # if intdiff_x < 0 :
            #     intdiff_x =0
            # if intdiff_y >100 :
            #     intdiff_y =100
            # if intdiff_y < 0 :
            #     intdiff_y =0
            intdiff_x = max(0, min(100, intdiff_x))
            intdiff_y = max(0, min(100, intdiff_y))

            try:
                plc.write_by_name('MAIN.VISION_IDX', int(label), pyads.PLCTYPE_INT)
                plc.write_by_name('MAIN.VISION_X', intdiff_x, pyads.PLCTYPE_INT)
                plc.write_by_name('MAIN.VISION_Y', intdiff_y, pyads.PLCTYPE_INT)
                plc.write_by_name('MAIN.VISION_LOCK', self.vision_lock, pyads.PLCTYPE_BOOL)
                plc.write_by_name('MAIN.VISION_SWING', 1 if swinging else 0, pyads.PLCTYPE_BOOL)
                # 新增：发送人体数量
                # plc.write_by_name('MAIN.VISION_PERSON_COUNT', self.person_count, pyads.PLCTYPE_INT)
            except ValueError:
                self.send_to_txt_browser.emit(f"plc发送失败")

            # packet = f"{label}-{intdiff_x}-{intdiff_y}"
            # 输出日志
            packet = f"动作:{label}, X:{intdiff_x}, Y:{intdiff_y}, 锁定:{self.vision_lock}, 晃动:{swinging}, 人数:{self.person_count}"
            self.send_to_txt_browser.emit(packet)
            time.sleep(1)


    def run_base(self):

        plc = pyads.Connection('5.157.109.58.1.1', 851)
        #plc.open()
        # diff_x = 3
        # diff_y = 5
        #
        # plc.write_by_name('MAIN.VISION_IDX', diff_x, pyads.PLCTYPE_INT)
        # plc.write_by_name('MAIN.VISION_X', diff_y, pyads.PLCTYPE_INT)
        # plc.write_by_name('MAIN.VISION_Y', 6, pyads.PLCTYPE_INT)
        #
        # test_int1 = plc.read_by_name('MAIN.VISION_IDX', pyads.PLCTYPE_INT)
        # test_int2 = plc.read_by_name('MAIN.VISION_X', pyads.PLCTYPE_INT)
        # test_int3 = plc.read_by_name('MAIN.VISION_Y', pyads.PLCTYPE_INT)
        # print(test_int1, test_int2, test_int3)



        retry_count = 0
        max_retries = 5
        retry_delay = 1  # 重试间隔时间（秒）

        # for i in range(5):
        #     if not self.connected:
        #         try:
        #             # 关闭旧连接
        #             if plc:
        #                 plc.close()
        #
        #             # 尝试建立新连接
        #             self.plc_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #             self.plc_socket.settimeout(5)  # 设置连接超时时间
        #             self.plc_socket.connect((self.ip, self.port))
        #             self.plc_socket.settimeout(None)  # 连接成功后取消超时设置
        #             self.connected = True
        #             retry_count = 0  # 重置重试计数器
        #             self.send_to_txt_browser.emit("Connected to PLC successfully")
        #         except socket.error as e:
        #             error_msg = f"连接失败 ({retry_count}/{max_retries}): {str(e)}"
        #             self.send_to_txt_browser.emit(error_msg)
        #             self.connected = False
        #             retry_count += 1
        #
        #             if retry_count > max_retries:
        #                 self.send_to_txt_browser.emit("尝试连接plc最大次数到达, 中断线程")
        #                 # self.plcthread_state.emit()
        #
        #             time.sleep(retry_delay)
        #         else:
        #             break

        # 连接重试循环
        while self.running and retry_count <= max_retries:
            if not self.connected:
                try:
                    # 关闭旧连接
                    if self.plc_connection:
                        self.plc_connection.close()

                    # 尝试打开连接
                    self.plc.open()

                    # 验证连接状态
                    if self.plc.is_open:
                        self.connected = True
                        retry_count = 0  # 重置重试计数器
                        self.connection_state_changed.emit(True)
                        self.send_to_txt_browser.emit(f"成功连接到PLC: {self.ams_net_id}:{self.ams_port}")
                    else:
                        raise Exception("连接已打开但状态异常")

                except Exception as e:
                    error_msg = f"连接失败 ({retry_count}/{max_retries}): {str(e)}"
                    self.send_to_txt_browser.emit(error_msg)
                    self.connected = False
                    retry_count += 1

                    if retry_count > max_retries:
                        self.send_to_txt_browser.emit("尝试连接PLC最大次数到达, 中断线程")
                        self.connection_state_changed.emit(False)
                        break

                    time.sleep(retry_delay)

            # 如果已连接，则执行数据发送循环
            if self.connected:
                try:
                    self.send_plc_data()
                    time.sleep(0.05)  # 控制发送频率
                except Exception as e:
                    self.send_to_txt_browser.emit(f"数据发送错误: {str(e)}")
                    self.connected = False
                    self.connection_state_changed.emit(False)
                    # 不增加重试计数，下次循环会尝试重连

        while self.running:
            # print(self.visual_plc_data[0],self.visual_plc_data[1],self.visual_plc_data[2])
            label = next((num for num, action in self.action_label_map.items() if action == self.visual_plc_data[0]), None)
            # print(label)
            if label is not None:
                label = f"{int(label):03}"
            else:
                label = "eee"
            try:
                diff_x = int(self.visual_plc_data[1])
                if abs(diff_x)<=999:
                    diff_x = ("0"+f"{abs(diff_x):03}") if diff_x <0 else ("1"+f"{diff_x:03}")
                else:
                    raise ValueError("diff_x必须在±999之内")
                # diff_x = f"{diff_x:03}"
            except ValueError:
                diff_x = "eeee"
            try:
                diff_y = int(self.visual_plc_data[2])
                if abs(diff_y)<=999:
                    diff_y = ("0"+f"{abs(diff_y):03}") if diff_y <0 else ("1"+f"{diff_y:03}")
                else:
                    raise ValueError("diff_y必须在±999之内")
                # diff_y = f"{diff_y:03}"
            except ValueError:
                diff_y = "eeee"

            try:
                action_voice = int(self.voice_plc_data[0])
                if action_voice<=999:
                    action_voice = f"{action_voice:03}"
                else:
                    raise ValueError("action_voice必须在±999之内")
            except ValueError:
                action_voice = "eee"
            try:
                length_wav = int(self.voice_plc_data[2])
                if length_wav<100:
                    length_wav = f"{length_wav:02}"
                else:
                    raise ValueError("音频长度不能超过100s")
            except ValueError:
                length_wav = "ee"
            try:
                anwser_chioce = int(self.voice_plc_data[1])
                if anwser_chioce == 0 or anwser_chioce == 1:
                    anwser_chioce = f"{anwser_chioce}"
                else:
                    raise ValueError("语音答案id只能是0或1")
            except ValueError:
                anwser_chioce = "e"

            # if self.previous_visual_plc_data != self.visual_plc_data or self.previous_voice_plc_data!= self.voice_plc_data:
            #     packet = f"{label}{diff_x}{diff_y}{action_voice}{length_wav}{anwser_chioce}00"
            #     # print(f"Sending packet: {packet}")
            #     self.send_to_txt_browser.emit(packet)
            #     self.plc_socket.sendall(packet.encode())
            #     self.previous_visual_plc_data = self.visual_plc_data
            #     self.previous_voice_plc_data = self.voice_plc_data
            packet = f"{label}{diff_x}{diff_y}{action_voice}{length_wav}{anwser_chioce}00"
            # print(f"Sending packet: {packet}")
            self.send_to_txt_browser.emit(packet)
            self.plc_socket.sendall(packet.encode())
            self.previous_visual_plc_data = self.visual_plc_data
            self.previous_voice_plc_data = self.voice_plc_data
            # packet = f"{label}{diff_x}{diff_y}{action_voice}{length_wav}{anwser_chioce}00"
            # print(f"Sending packet: {packet}")
            # self.send_to_txt_browser.emit(packet)
            # self.plc_socket.sendall(packet.encode())
            # self.previous_visual_plc_data = self.visual_plc_data
            # self.previous_voice_plc_data = self.voice_plc_data
            time.sleep(0.05)

    def update_swing_detection(self, current_x):
        """更新并检测是否在左右晃动"""
        # 1. 更新历史数据
        self.x_history.append(current_x)
        if len(self.x_history) > self.max_history_size:
            self.x_history.pop(0)

        # 如果数据点太少，无法判断
        if len(self.x_history) < 3:
            return False

        # 2. 计算当前移动方向
        current_direction = 0
        # 使用最近几个点计算平均变化，减少噪声影响
        if len(self.x_history) >= 3:
            # 计算最近3个点的趋势
            recent_change = self.x_history[-1] - self.x_history[-3]
            if abs(recent_change) > self.min_movement_threshold:
                current_direction = 1 if recent_change > 0 else -1

        # 3. 检测方向变化
        if current_direction != 0 and current_direction != self.last_direction:
            # 方向发生改变（从左到右或从右到左）
            if self.last_direction != 0:  # 排除从静止到移动的情况
                self.swing_count += 1

        # 4. 更新上一次的方向
        self.last_direction = current_direction

        # 5. 判断是否在晃动（基于最近N次方向变化）
        # 创建一个滑动窗口来分析方向变化频率
        window_size = min(15, len(self.x_history) - 2)  # 分析窗口大小
        if window_size >= 5:  # 至少有5个点才能分析
            # 计算窗口内的方向变化次数
            window_swing_count = 0
            window_directions = []

            # 计算窗口中每个点的方向
            for i in range(len(self.x_history) - window_size, len(self.x_history) - 1):
                change = self.x_history[i + 1] - self.x_history[i]
                if abs(change) > self.min_movement_threshold:
                    direction = 1 if change > 0 else -1
                else:
                    direction = 0
                window_directions.append(direction)

            # 统计窗口内的方向变化次数
            for i in range(1, len(window_directions)):
                if window_directions[i] != 0 and window_directions[i] != window_directions[i - 1]:
                    window_swing_count += 1

            # 判断是否在晃动
            old_swinging_state = self.is_swinging
            self.is_swinging = window_swing_count >= self.swing_threshold

            # 如果晃动状态发生变化，发送通知
            if old_swinging_state != self.is_swinging:
                if self.is_swinging:
                    self.send_to_txt_browser.emit("检测到目标在左右晃动")
                else:
                    self.send_to_txt_browser.emit("目标停止晃动")

        return self.is_swinging

    def stop(self):
        self.running = False


