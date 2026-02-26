# PLC1.py 完整修改版本

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import socket
import time
import pyads
from sqlalchemy import false


class plc_thread(QThread):
    send_to_txt_browser = pyqtSignal(str)
    # 可以添加一个信号用于发送属性识别状态
    attributes_data_updated = pyqtSignal(dict)

    def __init__(self, ip, port):
        super().__init__()
        self.testItem = 1  # 测试
        self.running = True
        self.ip = ip
        self.port = port

        # ========== 原有视觉数据 ==========
        self.voice_plc_data = (1000, "invalid", 100)
        self.visual_plc_data = ("invalid_action", 1000, 1000)

        # ========== 新增：人物属性数据 ==========
        self.person_attributes_data = {
            'color': '未知',
            'color_code': 0,  # 颜色编码 (0-7)
            'attributes_bits_low': 0,  # 属性低16位 (属性0-15)
            'attributes_bits_high': 0,  # 属性高16位 (属性16-25)
            'attributes_count': 0,  # 超过阈值的属性数量
            'timestamp': 0,  # 时间戳
            'valid': False  # 数据是否有效
        }

        # 颜色编码映射 (与MainFromNew.py保持一致)
        self.color_mapping = {
            '红': 1, '黄': 2, '蓝': 3, '绿': 4,
            '黑': 5, '白': 6, '紫': 7, '未知': 0,
            '未能识别': 0, '无': 0
        }

        # 属性位映射 (26个属性，每个对应一个bit位)
        # 注意：这个映射必须与person_attributes.py中的LABELS顺序完全一致！
        self.attribute_bit_mapping = {
            # 属性索引: (寄存器位位置, 说明)
            0: (0, "Hat-帽子"),
            1: (1, "Glasses-眼镜"),
            2: (2, "ShortSleeve-短袖"),
            3: (3, "LongSleeve-长袖"),
            4: (4, "UpperStride-上衣条纹"),
            5: (5, "UpperLogo-上衣Logo"),
            6: (6, "UpperPlaid-上衣格子"),
            7: (7, "UpperSplice-上衣拼接"),
            8: (8, "LowerStripe-下身条纹"),
            9: (9, "LowerPattern-下身图案"),
            10: (10, "LongCoat-长外套"),
            11: (11, "Trousers-长裤"),
            12: (12, "Shorts-短裤"),
            13: (13, "Skirt&Dress-裙子"),
            14: (14, "boots-靴子"),
            15: (15, "HandBag-手提包"),
            16: (0, "ShoulderBag-单肩包"),  # 高16位，从0开始
            17: (1, "Backpack-双肩包"),
            18: (2, "HoldObjectsInFront-正面持物"),
            19: (3, "AgeOver60-大于60岁"),
            20: (4, "Age18-60-18-60岁"),
            21: (5, "AgeLess18-小于18岁"),
            22: (6, "Female-女性"),
            23: (7, "Front-朝向:前"),
            24: (8, "Side-朝向:侧"),
            25: (9, "Back-朝向:后")
        }

        # 数组索引 0-25，对应26个属性，顺序必须与person_attributes.py中的LABELS保持一致
        self.attribute_array_mapping = [
            # 索引: (属性英文名, 属性中文名)
            (0, "Hat", "帽子"),
            (1, "Glasses", "眼镜"),
            (2, "ShortSleeve", "短袖"),
            (3, "LongSleeve", "长袖"),
            (4, "UpperStride", "上衣条纹"),
            (5, "UpperLogo", "上衣Logo"),
            (6, "UpperPlaid", "上衣格子"),
            (7, "UpperSplice", "上衣拼接"),
            (8, "LowerStripe", "下身条纹"),
            (9, "LowerPattern", "下身图案"),
            (10, "LongCoat", "长外套"),
            (11, "Trousers", "长裤"),
            (12, "Shorts", "短裤"),
            (13, "Skirt&Dress", "裙子"),
            (14, "boots", "靴子"),
            (15, "HandBag", "手提包"),
            (16, "ShoulderBag", "单肩包"),
            (17, "Backpack", "双肩包"),
            (18, "HoldObjectsInFront", "正面持物"),
            (19, "AgeOver60", "大于60岁"),
            (20, "Age18-60", "18-60岁"),
            (21, "AgeLess18", "小于18岁"),
            (22, "Female", "女性"),
            (23, "Front", "朝向:前"),
            (24, "Side", "朝向:侧"),
            (25, "Back", "朝向:后")
        ]
        # 新增：存储BOOL数组
        self.attributes_bool_array = [0] * 26  # 初始化为26个0

        # 原有晃动检测相关参数
        self.x_history = []
        self.max_history_size = 20
        self.swing_threshold = 5
        self.min_movement_threshold = 30
        self.is_swinging = False
        self.swing_count = 0
        self.last_direction = 0

        # 通信连接相关
        self.plc_socket = None
        self.previous_visual_plc_data = None
        self.previous_voice_plc_data = None
        self.connected = False

        # 新增：存储检测到的人体数量
        self.person_count = 0

        # 新增：属性数据发送计数器（控制发送频率）
        self.attributes_send_counter = 0
        self.attributes_send_interval = 2  # 每2个视觉周期发送一次属性数据

        # 行为标签映射
        self.action_label_map = {
            '0': 'cheer_up', '1': 'hand_waving', '2': 'jump_up', '3': 'phone_call',
            '4': 'pick_up', '5': 'play_with _phone', '6': 'sit_down', '7': 'squat_down',
            '8': 'stand', '9': 'taking_a_selfie', '10': 'walk'
        }

    # ========== 新增：人物属性数据处理方法 ==========

    def update_person_attributes(self, attributes_data):
        """
        更新人物属性数据，供主线程调用

        参数：
            attributes_data (dict): 从PersonAttributes模块返回的结果字典
        """
        # 先重置所有状态
        self.attributes_bool_array = [0] * 26
        self.person_attributes_data['valid'] = False

        if not attributes_data or 'summary' not in attributes_data:
            self.person_attributes_data['valid'] = False
            return

        try:
            summary = attributes_data['summary']
            color_result = attributes_data.get('color_result', {})


            # 1. 处理颜色
            color = summary.get('color', '未知')
            color_code = self.color_mapping.get(color, 0)

            # 3. 更新BOOL数组
            attr_result = attributes_data.get('attributes_result', {})
            above_threshold_indices = []
            if attr_result and attr_result.get('success'):
                above_threshold_indices = attr_result.get('above_threshold', [])

                for idx in above_threshold_indices:
                    if 0 <= idx < 26:
                        self.attributes_bool_array[idx] = 1  # 设置为1表示识别成功

            # 记录识别到的属性
            detected_attrs = []
            for idx in above_threshold_indices:
                if idx < len(self.attribute_array_mapping):
                    _, eng_name, chi_name = self.attribute_array_mapping[idx]
                    detected_attrs.append(f"{chi_name}")

            # 4. 更新数据
            self.person_attributes_data.update({
                'color': color,
                'color_code': color_code,
                'above_threshold_indices': above_threshold_indices,
                'attributes_count': len(above_threshold_indices),
                'bool_array': self.attributes_bool_array.copy(),  # 保存副本
                'timestamp': time.time(),
                'valid': True
            })

            # 4. 发送信号（可选，用于UI更新）???
            self.attributes_data_updated.emit(self.person_attributes_data.copy())

            # 5. 调试信息：显示哪些属性被识别
            if above_threshold_indices:
                attr_names = []
                for idx in above_threshold_indices:
                    if idx < len(self.attribute_array_mapping):
                        _, eng_name, chi_name = self.attribute_array_mapping[idx]
                        attr_names.append(f"{chi_name}({idx})")

                self.send_to_txt_browser.emit(
                    f"属性识别: 颜色{color}, 检测到属性: {', '.join(attr_names[:3])}" +
                    (f" 等{len(attr_names)}个" if len(attr_names) > 3 else "")
                )

        except Exception as e:
            self.send_to_txt_browser.emit(f"处理属性数据失败: {str(e)}")
            self.person_attributes_data['valid'] = False

    # ========== 修改原有的run方法 ==========

    def run(self):
        """主运行循环，连接PLC并发送数据"""
        plc = pyads.Connection('5.157.109.58.1.1', 851)
        retry_count = 0
        max_retries = 5
        retry_delay = 1

        # 连接重试循环
        while self.running and retry_count < max_retries:
            if not self.connected:
                try:
                    if plc:
                        plc.close()

                    plc.open()

                    if plc.is_open:
                        self.connected = True
                        retry_count = 0
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
                        break

                    time.sleep(retry_delay)

        # 主数据发送循环
        while self.running:
            try:
                # ========== 1. 处理视觉数据 ==========
                # 行为标签映射
                label = next(
                    (num for num, action in self.action_label_map.items()
                     if action == self.visual_plc_data[0]), None
                )
                if label is None or label == "":
                    label = 0

                # 计算偏移量
                try:
                    diff_x = int(self.visual_plc_data[1])
                except ValueError:
                    diff_x = 0
                try:
                    diff_y = int(self.visual_plc_data[2])
                except ValueError:
                    diff_y = 0

                intdiff_x = int(((diff_x + 450) / 900) * 100)
                intdiff_y = int(((diff_y + 400) / 800) * 100)
                intdiff_y = 100 - intdiff_y

                # 晃动检测
                swinging = False
                if self.vision_lock == 1:
                    swinging = self.update_swing_detection(intdiff_x)
                else:
                    self.x_history = []
                    self.swing_count = 0
                    self.last_direction = 0
                    if self.is_swinging:
                        self.is_swinging = False

                # 偏移量变换
                intxMin = 40
                intxMax = 80

                if intxMin <= intdiff_x <= intxMax:
                    intdiff_x = int((intdiff_x - intxMin) * (100 / (intxMax - intxMin)))
                elif intdiff_x < intxMin:
                    intdiff_x = 0
                else:
                    intdiff_x = 100

                # 确保值在0-100范围内
                intdiff_x = max(0, min(100, intdiff_x))
                intdiff_y = max(0, min(100, intdiff_y))

                # ========== 2. 发送视觉数据到PLC ==========
                plc.write_by_name('MAIN.VISION_IDX', int(label), pyads.PLCTYPE_INT)
                plc.write_by_name('MAIN.VISION_X', intdiff_x, pyads.PLCTYPE_INT)
                plc.write_by_name('MAIN.VISION_Y', intdiff_y, pyads.PLCTYPE_INT)
                plc.write_by_name('MAIN.VISION_LOCK', self.vision_lock, pyads.PLCTYPE_BOOL)
                plc.write_by_name('MAIN.VISION_SWING', 1 if swinging else 0, pyads.PLCTYPE_BOOL)

                # ========== 3. 发送人物属性数据到PLC ==========
                # 控制发送频率：每N个周期发送一次
                self.attributes_send_counter += 1
                if self.attributes_send_counter >= self.attributes_send_interval:
                    self.attributes_send_counter = 0

                    # 发送属性数据
                    # self._send_attributes_to_plc(plc)

                # ========== 4. 输出日志 ==========
                packet = (
                    f"动作:{label}, X:{intdiff_x}, Y:{intdiff_y}, "
                    f"锁定:{self.vision_lock}, 晃动:{swinging}, 人数:{self.person_count}"
                )

                # 如果发送了属性数据，添加到日志
                if self.attributes_send_counter == 0 and self.person_attributes_data['valid']:
                    packet += (
                        f", 颜色:{self.person_attributes_data['color']}({self.person_attributes_data['color_code']}), "
                        f"属性:{self.person_attributes_data['attributes_count']}个"
                    )

                self.send_to_txt_browser.emit(packet)

                # ========== 5. 休眠（控制发送频率） ==========
                time.sleep(1)  # 原有视觉数据发送频率

            except Exception as e:
                self.send_to_txt_browser.emit(f"PLC通信错误: {str(e)}")
                self.connected = False
                break

    # ========== 原有辅助方法 ==========

    def update_swing_detection(self, current_x):
        """更新并检测是否在左右晃动（原有方法）"""
        self.x_history.append(current_x)
        if len(self.x_history) > self.max_history_size:
            self.x_history.pop(0)

        if len(self.x_history) < 3:
            return False

        current_direction = 0
        if len(self.x_history) >= 3:
            recent_change = self.x_history[-1] - self.x_history[-3]
            if abs(recent_change) > self.min_movement_threshold:
                current_direction = 1 if recent_change > 0 else -1

        if current_direction != 0 and current_direction != self.last_direction:
            if self.last_direction != 0:
                self.swing_count += 1

        self.last_direction = current_direction

        window_size = min(15, len(self.x_history) - 2)
        if window_size >= 5:
            window_swing_count = 0
            window_directions = []

            for i in range(len(self.x_history) - window_size, len(self.x_history) - 1):
                change = self.x_history[i + 1] - self.x_history[i]
                if abs(change) > self.min_movement_threshold:
                    direction = 1 if change > 0 else -1
                else:
                    direction = 0
                window_directions.append(direction)

            for i in range(1, len(window_directions)):
                if window_directions[i] != 0 and window_directions[i] != window_directions[i - 1]:
                    window_swing_count += 1

            old_swinging_state = self.is_swinging
            self.is_swinging = window_swing_count >= self.swing_threshold

            if old_swinging_state != self.is_swinging:
                if self.is_swinging:
                    self.send_to_txt_browser.emit("检测到目标在左右晃动")
                else:
                    self.send_to_txt_browser.emit("目标停止晃动")

        return self.is_swinging

    # ========== 原有setter方法 ==========

    def set_person_count(self, count):
        """设置人体数量"""
        self.person_count = count

    def stop(self):
        """停止线程"""
        self.running = False

    # ========== 发送属性至plc ==========
    def _send_attributes_to_plc(self, plc):
        """
        发送属性数据到PLC
        使用BOOL数组格式
        """
        if not self.person_attributes_data['valid']:
            return

        try:
            # 1. 发送颜色编码
            color_code = self.person_attributes_data['color_code']
            plc.write_by_name('MAIN.ATTR_COLOR', color_code, pyads.PLCTYPE_INT)

            # 2. 发送BOOL数组 (26个BOOL值)
            # 注意：pyads可能不支持直接发送BOOL数组，可以转换为INT数组
            # 每个位置：0=未识别，1=识别

            # # 方案A：逐个发送BOOL值（兼容性好）
            # for i in range(26):
            #     reg_name = f'MAIN.ATTR_{i:02d}'  # 如 MAIN.ATTR_00
            #     bool_value = 1 if self.attributes_bool_array[i] else 0
            #     plc.write_by_name(reg_name, bool_value, pyads.PLCTYPE_BOOL)

            # 或者方案B：发送INT数组（如果PLC支持）
            plc.write_by_name('MAIN.ATTR_ARRAY', self.attributes_bool_array, pyads.PLCTYPE_ARR_INT)

            # # 3. 发送识别到的属性数量
            # attr_count = self.person_attributes_data['attributes_count']
            # plc.write_by_name('MAIN.ATTR_COUNT', attr_count, pyads.PLCTYPE_INT)
            #
            # 4. 发送数据有效标志
            plc.write_by_name('MAIN.ATTR_VALID', 1, pyads.PLCTYPE_BOOL)

            # 5. 记录发送状态（可选）
            # if attr_count > 0:
            #     # 找到被识别的属性索引
            #     detected_indices = [i for i, val in enumerate(self.attributes_bool_array) if val]
            #     self.send_to_txt_browser.emit(
            #         f"属性数据已发送: 颜色{self.person_attributes_data['color']}({color_code}), " +
            #         f"识别{attr_count}个属性"
            #     )

        except Exception as e:
            self.send_to_txt_browser.emit(f"发送属性数据失败: {e}")