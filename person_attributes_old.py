"""
人物属性识别模块 (PersonAttributes)
功能：封装了go.py中的所有核心功能，包括上衣颜色分析和26种属性识别。
设计原则：独立、可复用、线程安全，便于集成到实时系统中。
"""

import os
import cv2
import numpy as np
import paddle.inference as paddle_infer
from collections import Counter


class PersonAttributes:
    """
    人物属性识别器
    输入：人物图像 (通常是从摄像头画面中截取的目标边界框)
    输出：上衣颜色 + 26种属性的概率
    """

    def __init__(self, model_dir, label_map=None, threshold=0.65, use_gpu=True):
        """
        初始化识别器

        参数：
            model_dir (str): 包含 inference.pdmodel 和 inference.pdiparams 的模型目录路径
            label_map (dict): 属性标签映射，键为英文标签，值为中文标签。若为None，使用默认值。
            threshold (float): 属性判定的概率阈值，默认0.65
            use_gpu (bool): 是否使用GPU进行推理
        """
        self.model_dir = model_dir
        self.THRESHOLD = threshold

        # 1. 定义属性标签（与go.py保持一致）
        if label_map is None:
            # 默认标签映射，与go.py中的LABEL_MAP一致
            self.LABEL_MAP = {
                "Hat": "帽子", "Glasses": "眼镜", "ShortSleeve": "短袖", "LongSleeve": "长袖",
                "UpperStride": "上衣条纹", "UpperLogo": "上衣Logo", "UpperPlaid": "上衣格子", "UpperSplice": "上衣拼接",
                "LowerStripe": "下身条纹", "LowerPattern": "下身图案", "LongCoat": "长外套", "Trousers": "长裤",
                "Shorts": "短裤", "Skirt&Dress": "裙子", "boots": "靴子", "HandBag": "手提包",
                "ShoulderBag": "单肩包", "Backpack": "双肩包", "HoldObjectsInFront": "正面持物",
                "AgeOver60": "大于60岁", "Age18-60": "18-60岁", "AgeLess18": "小于18岁",
                "Female": "女性", "Front": "朝向:前", "Side": "朝向:侧", "Back": "朝向:后"
            }
        else:
            self.LABEL_MAP = label_map

        self.LABELS = list(self.LABEL_MAP.keys())  # 固定顺序的属性英文名列表

        # 2. 颜色范围定义 (HSV空间)
        self.COLOR_RANGES = {
            "黑": ([0, 0, 0], [180, 255, 40]),
            "白": ([0, 0, 180], [180, 40, 255]),
            "紫": ([115, 20, 30], [165, 255, 255]),
            "红1": ([0, 43, 46], [10, 255, 255]),
            "红2": ([156, 43, 46], [180, 255, 255]),
            "绿": ([35, 43, 46], [77, 255, 255]),
            "蓝": ([90, 43, 46], [115, 255, 255]),
            "黄": ([26, 43, 46], [34, 255, 255]),
        }

        # 3. 延迟初始化模型预测器（第一次调用时再加载，避免启动过慢）
        self.predictor = None
        self.use_gpu = use_gpu
        self._model_loaded = False

    def _init_predictor(self):
        """
        初始化PaddlePaddle推理预测器。
        私有方法，在首次需要推理时自动调用。
        """
        if self._model_loaded:
            return

        model_file = os.path.join(self.model_dir, "inference.pdmodel")
        params_file = os.path.join(self.model_dir, "inference.pdiparams")

        if not os.path.exists(model_file):
            raise FileNotFoundError(f"模型结构文件不存在: {model_file}")
        if not os.path.exists(params_file):
            raise FileNotFoundError(f"模型参数文件不存在: {params_file}")

        # 配置推理参数
        config = paddle_infer.Config(model_file, params_file)

        # 设置GPU/CPU
        if self.use_gpu:
            config.enable_use_gpu(100, 0)  # 使用GPU，初始显存100MB，设备号0
        else:
            config.disable_gpu()
            config.set_cpu_math_library_num_threads(4)  # 设置CPU线程数

        config.switch_ir_optim(True)  # 开启图优化
        config.disable_glog_info()  # 关闭冗余日志

        # 创建预测器
        self.predictor = paddle_infer.create_predictor(config)
        self._model_loaded = True
        print(f"人物属性识别模型加载成功，使用{'GPU' if self.use_gpu else 'CPU'}推理")

    # ==================== 上衣颜色分析相关方法 ====================

    def _get_single_patch_color(self, patch_img):
        """
        分析单个小区域的主颜色（从go.py的get_single_patch_color移植）

        参数：
            patch_img: 小区域的BGR图像

        返回：
            str: 颜色名称（"黑"、"白"、"红"等）或 "未知"/"无"
        """
        if patch_img.size == 0:
            return "未知"

        # 转换到HSV颜色空间，对颜色更敏感
        hsv = cv2.cvtColor(patch_img, cv2.COLOR_BGR2HSV)

        max_pixels = 0
        best_color = "无"

        # 遍历所有预定义的颜色范围
        for name, (lower, upper) in self.COLOR_RANGES.items():
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
            count = cv2.countNonZero(mask)

            # 如果该颜色像素数最多且超过阈值（避免噪声）
            if count > max_pixels and count > 10:
                max_pixels = count
                best_color = name.replace("1", "").replace("2", "").replace("_", "")

        return best_color

    def analyze_clothing_color(self, img, draw_on_img=False):
        """
        分析上衣颜色主函数（从go.py的analyze_clothing_color_9_points移植）

        参数：
            img: 完整的BGR人物图像
            draw_on_img: 是否在图像上绘制采样点（用于调试）

        返回：
            tuple: (final_color, votes)
                - final_color (str): 最终判定的颜色
                - votes (list): 9个采样点的颜色投票详情
        """
        h, w, _ = img.shape

        # 1. 定义上衣大致区域（根据人体比例估计）
        y_min, y_max = int(h * 0.2), int(h * 0.55)  # 从15%到60%高度
        x_min, x_max = int(w * 0.15), int(w * 0.85)  # 从20%到80%宽度

        shirt_h = y_max - y_min
        shirt_w = x_max - x_min

        # 2. 在上衣区域定义3x3网格采样点
        #grid_ratios = [0.35, 0.50, 0.65]
        grid_ratios = [0.2, 0.4, 0.6, 0.8]
        patch_size = min(shirt_w, shirt_h) // 8  # 采样点大小
        half_p = patch_size // 2

        votes = []  # 存储9个点的颜色判定结果

        # 3. 遍历9个采样点
        for py in grid_ratios:
            for px in grid_ratios:
                cx = int(x_min + shirt_w * px)  # 采样点中心x
                cy = int(y_min + shirt_h * py)  # 采样点中心y

                # 计算采样区域边界
                x1, y1 = max(0, cx - half_p), max(0, cy - half_p)
                x2, y2 = min(w, cx + half_p), min(h, cy + half_p)

                # 提取小区域并分析颜色
                patch = img[y1:y2, x1:x2]
                color = self._get_single_patch_color(patch)
                votes.append(color)

                # 可选：在图像上标记采样点（调试用）
                if draw_on_img:
                    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 255), 2)
                    cv2.circle(img, (cx, cy), 2, (0, 0, 255), -1)

        # 4. 投票决定最终颜色（排除无效票）
        valid_votes = [v for v in votes if v not in ["无", "未知"]]

        if not valid_votes:
            final_color = "未能识别"
        else:
            counter = Counter(valid_votes)
            final_color = counter.most_common(1)[0][0]  # 取票数最多的颜色

        print(f"最终识别颜色: {str(final_color)}")

        return final_color, votes

    # ==================== 26种属性识别相关方法 ====================

    def _preprocess(self, img):
        """
        图像预处理（从go.py的preprocess函数移植）
        将输入图像转换为模型需要的格式

        参数：
            img: BGR格式的输入图像

        返回：
            numpy.ndarray: 预处理后的4维数组 [1, 3, 256, 192]
        """
        # 1. 调整尺寸到模型输入大小
        img = cv2.resize(img, (192, 256))  # 注意：宽192，高256

        # 2. 转换颜色通道 BGR -> RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # 3. 归一化到 [0, 1]
        img = img.astype("float32") / 255.0

        # 4. 使用ImageNet的均值和标准差进行标准化
        mean = np.array([0.485, 0.456, 0.406]).astype("float32").reshape((1, 1, 3))
        std = np.array([0.229, 0.224, 0.225]).astype("float32").reshape((1, 1, 3))
        img = (img - mean) / std

        # 5. 调整维度顺序: HWC -> CHW，并添加批次维度
        # 最终形状: [1, 3, 256, 192]
        return img.transpose((2, 0, 1))[np.newaxis, :].astype("float32")

    def analyze_attributes(self, img):
        """
        分析26种人物属性

        参数：
            img: BGR格式的人物图像

        返回：
            dict: 包含以下键值：
                - 'probs' (numpy.ndarray): 26个属性的概率值，范围[0, 1]
                - 'labels' (list): 26个属性的英文标签（固定顺序）
                - 'label_map' (dict): 英文到中文的标签映射
                - 'threshold' (float): 使用的阈值
                - 'above_threshold' (list): 超过阈值的属性索引列表
        """
        # 确保预测器已初始化
        if self.predictor is None:
            self._init_predictor()

        # 1. 预处理
        input_data = self._preprocess(img)

        # 2. 获取输入输出句柄
        input_names = self.predictor.get_input_names()
        input_handle = self.predictor.get_input_handle(input_names[0])

        # 3. 将数据拷贝到模型输入
        input_handle.copy_from_cpu(input_data)

        # 4. 执行推理
        self.predictor.run()

        # 5. 获取输出
        output_names = self.predictor.get_output_names()
        output_handle = self.predictor.get_output_handle(output_names[0])
        output_data = output_handle.copy_to_cpu()  # 形状: [1, 26]

        # 6. 提取第一个样本的26个值（去掉批次维度）
        logits = output_data[0]  # 形状: [26,]

        # 7. 通过Sigmoid函数将logits转换为概率
        # 注意：这是多标签分类，每个属性独立，所以用Sigmoid而不是Softmax
        probs = 1 / (1 + np.exp(-logits))

        # 8. 找出超过阈值的属性
        above_threshold = np.where(probs > self.THRESHOLD)[0].tolist()

        return {
            'probs': probs,
            'labels': self.LABELS,
            'label_map': self.LABEL_MAP,
            'threshold': self.THRESHOLD,
            'above_threshold': above_threshold
        }

    # ==================== 综合分析方法 ====================

    def analyze_full(self, img, analyze_color=True, analyze_attributes=True):
        """
        完整的人物属性分析（颜色 + 26种属性）

        参数：
            img: BGR格式的人物图像
            analyze_color: 是否分析上衣颜色
            analyze_attributes: 是否分析26种属性

        返回：
            dict: 分析结果，结构如下：
            {
                'color_result': {
                    'final_color': '红色',
                    'votes': ['红', '红', '红', ...],  # 9个采样点颜色
                    'success': True/False
                },
                'attributes_result': {
                    'probs': [0.95, 0.23, ...],  # 26个概率值
                    'labels': ['Hat', 'Glasses', ...],
                    'above_threshold': [0, 3, 5],  # 超过阈值的属性索引
                    'success': True/False
                },
                'summary': {
                    'color': '红色',
                    'main_attributes': ['帽子', '短袖'],  # 超过阈值的中文属性
                    'timestamp': '2024-01-27 14:30:00'
                }
            }
        """
        import datetime

        result = {
            'color_result': None,
            'attributes_result': None,
            'summary': {
                'color': '未知',
                'main_attributes': [],
                'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }

        try:
            # 1. 分析上衣颜色
            if analyze_color and img is not None and img.size > 0:
                final_color, votes = self.analyze_clothing_color(img.copy())
                result['color_result'] = {
                    'final_color': final_color,
                    'votes': votes,
                    'success': final_color != "未能识别"
                }
                result['summary']['color'] = final_color

            # 2. 分析26种属性
            if analyze_attributes and img is not None and img.size > 0:
                attr_result = self.analyze_attributes(img)
                result['attributes_result'] = {
                    'probs': attr_result['probs'].tolist(),  # 转换为列表便于序列化
                    'labels': attr_result['labels'],
                    'above_threshold': attr_result['above_threshold'],
                    'success': len(attr_result['above_threshold']) > 0
                }

                # 生成摘要：超过阈值的属性（转换为中文）
                main_attrs = []
                for idx in attr_result['above_threshold']:
                    if idx < len(self.LABELS):
                        eng_label = self.LABELS[idx]
                        chi_label = self.LABEL_MAP.get(eng_label, eng_label)
                        main_attrs.append(chi_label)
                result['summary']['main_attributes'] = main_attrs

        except Exception as e:
            print(f"人物属性分析失败: {str(e)}")
            # 确保结果字典结构完整
            if result['color_result'] is None:
                result['color_result'] = {'success': False, 'error': str(e)}
            if result['attributes_result'] is None:
                result['attributes_result'] = {'success': False, 'error': str(e)}

        return result

    # ==================== 工具方法 ====================

    def get_color_result_text(self, color_result):
        """生成颜色结果的文本描述"""
        if not color_result or not color_result.get('success'):
            return "上衣颜色: 识别失败"

        votes_str = ",".join(color_result['votes'][:5]) + " | " + ",".join(color_result['votes'][5:])
        return f"上衣颜色: {color_result['final_color']} (采样: {votes_str})"

    def get_attributes_result_text(self, attributes_result, max_display=5):
        """生成属性结果的文本描述"""
        if not attributes_result or not attributes_result.get('success'):
            return "属性识别: 无超过阈值属性"

        lines = ["识别属性:"]
        above_idx = attributes_result['above_threshold']
        labels = attributes_result['labels']
        probs = attributes_result['probs']

        # 显示概率最高的前几个属性
        for idx in above_idx[:max_display]:
            eng_label = labels[idx]
            chi_label = self.LABEL_MAP.get(eng_label, eng_label)
            prob = probs[idx]
            lines.append(f"  {chi_label}: {prob:.1%}")

        if len(above_idx) > max_display:
            lines.append(f"  等{len(above_idx)}个属性...")

        return "\n".join(lines)

    def get_summary_text(self, full_result):
        """生成综合摘要文本"""
        if not full_result:
            return "无分析结果"

        summary = full_result['summary']
        color = summary['color']
        main_attrs = summary['main_attributes'][:3]  # 只取前3个主要属性

        if not main_attrs:
            return f"上衣{color}，无明显特征属性"
        else:
            attrs_str = "、".join(main_attrs)
            return f"上衣{color}，特征: {attrs_str}"


# ==================== 独立测试函数 ====================
def test_standalone():
    """独立测试函数，验证模块是否能正常工作"""
    import sys

    # 1. 设置模型路径（需要根据实际情况修改）
    MODEL_DIR = r"D:\01AIWorkSpace\Test\PaddleClas-release-2.6(0113)\output\PPLCNet_x1_0\best_model"
    TEST_IMAGE = r"D:\01AIWorkSpace\Test\PaddleClas-release-2.6(0113)\pulc_demo_imgs\person_attribute\090007.jpg"

    if not os.path.exists(MODEL_DIR):
        print(f"错误：模型目录不存在 - {MODEL_DIR}")
        return

    if not os.path.exists(TEST_IMAGE):
        print(f"错误：测试图片不存在 - {TEST_IMAGE}")
        return

    # 2. 创建识别器实例
    print("正在初始化人物属性识别器...")
    detector = PersonAttributes(model_dir=MODEL_DIR, use_gpu=True)

    # 3. 加载测试图片
    print(f"正在加载测试图片: {TEST_IMAGE}")
    img = cv2.imread(TEST_IMAGE)
    if img is None:
        print("错误：无法读取图片")
        return

    # 4. 执行完整分析
    print("正在进行人物属性分析...")
    result = detector.analyze_full(img)

    # 5. 打印结果
    print("\n" + "=" * 50)
    print("人物属性分析结果:")
    print("=" * 50)

    # 颜色结果
    color_text = detector.get_color_result_text(result['color_result'])
    print(f"\n{color_text}")

    # 属性结果
    attr_text = detector.get_attributes_result_text(result['attributes_result'])
    print(f"\n{attr_text}")

    # 综合摘要
    summary_text = detector.get_summary_text(result)
    print(f"\n综合摘要: {summary_text}")

    # 6. 详细概率列表（可选）
    print("\n详细概率列表:")
    print("-" * 40)
    if result['attributes_result'] and result['attributes_result']['success']:
        probs = result['attributes_result']['probs']
        labels = result['attributes_result']['labels']

        for i, (label, prob) in enumerate(zip(labels, probs)):
            chi_label = detector.LABEL_MAP.get(label, label)
            mark = "✓" if prob > detector.THRESHOLD else "✗"
            print(f"[{i:02d}] {chi_label:10s}: {prob:.3f} {mark}")


if __name__ == "__main__":
    # 如果直接运行此文件，执行独立测试
    test_standalone()