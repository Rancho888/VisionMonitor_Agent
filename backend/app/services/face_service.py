"""
人脸识别服务模块

核心职责:
    1. 人脸检测: 使用 InsightFace SCRFD 检测器识别画面中的人脸位置
    2. 特征提取: 使用 ArcFace 提取 512 维深度学习人脸特征向量
    3. 人脸注册: 将人员照片的人脸特征存入本地人像库 (pickle)
    4. 人脸识别: 将监控画面中的人脸与人像库比对，返回匹配结果

技术方案:
    - 主方案: InsightFace (SCRFD + ArcFace)
      - SCRFD: 专攻小脸 / 远距离目标的人脸检测器，比 RetinaFace 更快
      - ArcFace: 512 维深度学习特征，提供业界顶尖的识别精度
    - 兆底方案: OpenCV Haar Cascade + HSV/LBP 直方图特征
      - 当 InsightFace 初始化失败或检测异常时自动回退

特征比对算法:
    - 余弦相似度 (Cosine Similarity): 衡量两个特征向量的方向相似性
    - 识别阈值: 0.35 (经验值，ArcFace 特征通常在 0.3~0.8 之间分布)
      - < 0.35: 视为不匹配
      - ≥ 0.50: 高置信度匹配 (绿色标记)
      - 0.35~0.50: 中等置信度 (黄色标记)

依赖关系:
    - insightface: SCRFD + ArcFace 模型
    - OpenCV: 图像编解码、Haar Cascade 兆底
    - numpy: 向量运算与特征比对
    - pickle: 本地人像库持久化
"""
import os
import cv2
import numpy as np
import base64
import pickle
import threading
from typing import List, Dict, Any, Optional, Tuple

try:
    import insightface
    from insightface.app import FaceAnalysis
    INSIGHTFACE_AVAILABLE = True   # InsightFace 可用标志
except ImportError:
    INSIGHTFACE_AVAILABLE = False  # InsightFace 不可用，将回退到 Haar Cascade
    print("insightface 未安装，人脸识别功能不可用")


class FaceService:
    """
    人脸识别服务（基于 InsightFace SCRFD + ArcFace）

    核心职责:
        - 检测画面中的人脸位置 (bbox) 并提取特征向量
        - 管理人员人像库（注册 / 追加 / 删除）
        - 实时识别画面中的人脸身份

    设计模式:
        - 单例模式: 通过全局 face_service 实例访问
        - 策略模式: InsightFace 主方案 + Haar Cascade 兆底方案自动切换
        - 线程安全: _lock 串行化 InsightFace 推理，保证多摄像头线程安全

    使用方式:
        # 注册人脸
        face_service.register_face_from_bytes("张三", image_bytes)
        # 实时识别
        results = face_service.recognize_faces(frame)
    """

    def __init__(self, face_db_path: str = "./data/face_db"):
        """
        初始化人脸识别服务

        参数:
            face_db_path: 人像库存储路径，包含特征 pickle 文件和人员照片目录

        初始化流程:
            1. 创建人像库目录（若不存在）
            2. 初始化 InsightFace 模型 (SCRFD + ArcFace)
            3. 从磁盘加载已有的人像库数据
        """
        self.face_db_path = face_db_path
        # 已知人员: {name: {"features": [vec1, vec2, ...], "image_paths": [path1, path2, ...]}}
        self.known_persons: Dict[str, Dict] = {}
        # _lock: 串行化 InsightFace 推理，因为 ONNX Runtime 不支持多线程并发推理
        self._lock = threading.Lock()
        os.makedirs(face_db_path, exist_ok=True)

        # ========== InsightFace (SCRFD + ArcFace) 主方案 ==========
        # SCRFD: 人脸检测器，专攻小脸和远距离目标
        # ArcFace: 人脸识别器，提取 512 维深度学习特征向量
        self.app = None
        if INSIGHTFACE_AVAILABLE:
            try:
                # 模型配置说明:
                # - buffalo_sc: SCRFD 检测器 + ArcFace 识别的轻量级组合
                # - CPUExecutionProvider: 纯 CPU 推理，无需 GPU 依赖
                # - det_thresh=0.4: 检测置信度阈值，较低值提高对光照不佳/侧脸照片的兼容性
                # - det_max_num=0: 不限制检测人脸数量，支持多人场景
                # - det_size=(320, 320): 检测输入尺寸，平衡精度与速度
                self.app = FaceAnalysis(
                    name="buffalo_sc",          # SCRFD 检测器 + ArcFace 识别
                    providers=["CPUExecutionProvider"],
                    allowed_modules=["detection", "recognition"],
                    det_thresh=0.4,              # 检测阈值 0.4: 提高对光照不佳/侧脸照片的兼容性
                    det_max_num=0,               # 不限制检测人脸数量，支持多人场景
                )
                ctx_id = 0                       # 0 = CPU 推理，GPU 环境可用 -1 指定 CUDA
                # det_size=(320, 320): 检测输入分辨率，320px 在精度和速度之间取平衡
                self.app.prepare(ctx_id=ctx_id, det_size=(320, 320))
                print("✅ InsightFace 初始化成功 (SCRFD + ArcFace, 512维)")
            except Exception as e:
                print(f"⚠️ InsightFace 初始化失败: {e}")

        self._load_face_db()

    def _load_face_db(self):
        """
        从文件加载人像库 (pickle 格式)

        加载文件:
            {face_db_path}/face_db.pkl — 存储所有人员特征和图片路径
        """
        db_file = os.path.join(self.face_db_path, "face_db.pkl")
        if os.path.exists(db_file):
            with open(db_file, "rb") as f:
                self.known_persons = pickle.load(f)
            print(f"已加载 {len(self.known_persons)} 个人像特征")

    def _save_face_db(self):
        """
        保存人像库到文件 (pickle 格式)

        保存文件:
            {face_db_path}/face_db.pkl — 包含所有人员的特征向量和图片路径
        """
        db_file = os.path.join(self.face_db_path, "face_db.pkl")
        with open(db_file, "wb") as f:
            pickle.dump(self.known_persons, f)

    def get_persons_for_recovery(self) -> List[Dict[str, str]]:
        """
        从 pickle 读取所有人员信息，用于数据库恢复

        返回:
            List[Dict[str, str]]: 人员信息列表，每项包含:
                - name: 姓名
                - face_image_path: 第一张注册照片路径
                - face_encoding_path: 特征编码目录路径
                - category: 固定为 "staff"
                - department: 固定为空字符串
        """
        persons = []
        for name, data in self.known_persons.items():
            image_paths = data.get("image_paths", [])
            first_image = image_paths[0] if image_paths else ""
            persons.append({
                "name": name,
                "face_image_path": first_image,
                "face_encoding_path": os.path.join(self.face_db_path, name),
                "category": "staff",
                "department": "",
            })
        return persons

    # ==================== 特征提取（兆底方案）====================
    # 当 InsightFace 不可用或检测异常时，使用 HSV + LBP 直方图特征作为兆底

    def _extract_face_roi(self, frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> np.ndarray:
        """
        从画面中裁剪人脸区域并提取特征（兆底方案，仅在 InsightFace 不可用时使用）

        参数:
            frame: BGR 格式的图像数组
            bbox: (x, y, w, h) - 左上角坐标和宽高

        返回:
            np.ndarray: 64 维特征向量（32维 HSV 颜色直方图 + 32维 LBP 纹理直方图）

        特征组成:
            - HSV 颜色直方图 (32维): H(色相) + S(饱和度) 各 16 个 bin
            - LBP 纹理直方图 (32维): 局部二值模式，捕捉面部纹理特征
        """
        x, y, w, h = bbox
        x, y = max(0, x), max(0, y)
        face_roi = frame[y:y+h, x:x+w]

        if face_roi.size == 0:
            return np.zeros(64)

        # 缩放到统一尺寸
        face_roi = cv2.resize(face_roi, (128, 128))

        # 多维度特征：HSV 直方图 + LBP 纹理特征
        features = []

        # 1. HSV 颜色直方图（32维）
        hsv = cv2.cvtColor(face_roi, cv2.COLOR_BGR2HSV)
        for i, channel in enumerate([0, 1]):
            hist = cv2.calcHist([hsv], [channel], None, [16], [0, 256])
            hist = cv2.normalize(hist, hist).flatten()
            features.extend(hist)

        # 2. 局部二值模式（LBP）简化版（32维）
        gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        lbp = self._simple_lbp(gray)
        lbp_hist = cv2.calcHist([lbp], [0], None, [32], [0, 256])
        lbp_hist = cv2.normalize(lbp_hist, lbp_hist).flatten()
        features.extend(lbp_hist)

        return np.array(features, dtype=np.float32)

    def _simple_lbp(self, gray_img: np.ndarray) -> np.ndarray:
        """
        简化的 LBP (Local Binary Pattern) 纹理特征提取

        算法原理:
            将每个像素与周围 8 个邻域像素比较，大于等于中心点记 1，否则记 0，
            组合成 8 位二进制码，反映局部纹理模式。

        性能优化:
            使用 numpy 向量化位移运算代替双重 for 循环，速度提升 30~50 倍

        参数:
            gray_img: 灰度图像数组

        返回:
            np.ndarray: LBP 编码图像（尺寸比输入小 2 像素，因为边界无法计算）
        """
        h, w = gray_img.shape
        center = gray_img[1:h-1, 1:w-1]
        # 8 邻域比较，向量化位移运算
        code = np.zeros((h-2, w-2), dtype=np.uint8)
        code |= ((gray_img[0:h-2, 0:w-2] >= center).astype(np.uint8)) << 7
        code |= ((gray_img[0:h-2, 1:w-1] >= center).astype(np.uint8)) << 6
        code |= ((gray_img[0:h-2, 2:w]   >= center).astype(np.uint8)) << 5
        code |= ((gray_img[1:h-1, 2:w]   >= center).astype(np.uint8)) << 4
        code |= ((gray_img[2:h,   2:w]   >= center).astype(np.uint8)) << 3
        code |= ((gray_img[2:h,   1:w-1] >= center).astype(np.uint8)) << 2
        code |= ((gray_img[2:h,   0:w-2] >= center).astype(np.uint8)) << 1
        code |= ((gray_img[1:h-1, 0:w-2] >= center).astype(np.uint8)) << 0
        return code

    # ==================== 人脸检测 ====================

    def detect_faces(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        检测画面中的人脸（主方案 InsightFace + 兆底 Haar Cascade）

        检测流程:
            1. 尝试 InsightFace SCRFD 检测 + ArcFace 特征提取
            2. 失败时自动回退到 OpenCV Haar Cascade + 直方图特征

        参数:
            frame: BGR 格式的图像数组

        返回:
            List[Dict[str, Any]]: 检测到的人脸列表，每项包含:
                - bbox: (x, y, w, h) 左上角坐标和宽高
                - features: np.ndarray 特征向量 (ArcFace 512维 或 直方图 64维)
                - score: float 检测置信度

        线程安全:
            使用 self._lock 串行化 InsightFace 推理，防止多摄像头并发冲突
        """
        faces = []

        # ====== 方案1: InsightFace SCRFD + ArcFace (主方案) ======
        # SCRFD 专攻小脸/远距离目标，ArcFace 提供 512 维深度学习特征
        if self.app is not None:
            try:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # InsightFace 要求 RGB 输入
                with self._lock:  # 串行化推理，ONNX Runtime 不支持多线程并发
                    detections = self.app.get(rgb_frame, max_num=0)  # max_num=0: 不限制检测数量

                for face in detections:
                    bbox = face.bbox.astype(int)
                    x, y, x2, y2 = bbox
                    bw, bh = x2 - x, y2 - y

                    if bw < 10 or bh < 10:
                        continue  # 过滤过小的误检（< 10px 通常是噪声）

                    # ArcFace 512 维深度学习特征（主特征）
                    # embedding 和 normed_embedding 是 InsightFace 不同版本的属性名
                    features = None
                    if hasattr(face, "embedding") and face.embedding is not None:
                        features = face.embedding
                    elif hasattr(face, "normed_embedding") and face.normed_embedding is not None:
                        features = face.normed_embedding

                    # 兆底: 提取旧版 HSV+LBP 直方图特征（64维）
                    # 仅在 ArcFace 特征不可用时使用，精度较低
                    if features is None:
                        features = self._extract_face_roi(frame, (x, y, bw, bh))

                    det_score = float(face.det_score) if hasattr(face, "det_score") else 0.9

                    faces.append({
                        "bbox": (x, y, bw, bh),
                        "features": features,
                        "score": det_score,
                    })
                return faces
            except Exception as e:
                print(f"InsightFace 检测失败: {e}，回退 Haar Cascade")

        # ====== 兆底: OpenCV Haar Cascade ======
        # 当 InsightFace 不可用或检测异常时回退
        # scaleFactor=1.08: 较小的缩放比例提高检出率
        # minNeighbors=3: 较低的邻居阈值提高召回率（牺牲部分精度）
        # minSize=(40, 40): 最小检测尺寸，过滤过小的误检
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(cascade_path)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        detected = face_cascade.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=3, minSize=(40, 40))

        for (x, y, bw, bh) in detected:
            features = self._extract_face_roi(frame, (x, y, bw, bh))
            faces.append({"bbox": (x, y, bw, bh), "features": features, "score": 0.8})

        return faces

    # ==================== 人脸注册 ====================

    def register_face_from_bytes(self, name: str, image_bytes: bytes) -> bool:
        """
        通过内存 bytes 注册人脸（绕过 OpenCV 中文路径问题）

        注册流程:
            1. 将 bytes 解码为图像数组（避免 cv2.imread 不支持中文路径）
            2. 检测人脸并提取特征
            3. 若首次检测失败，尝试直方图均衡化增强后重试
            4. 保存照片和特征到本地人像库

        参数:
            name: 人员姓名（作为人像库的键）
            image_bytes: 图片二进制数据（JPEG / PNG 等常见格式）

        返回:
            bool: 注册成功返回 True，失败返回 False
        """
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                print("❌ 内存解码图片失败")
                return False

            print(f"📸 注册图片尺寸: {img.shape}")
            faces = self.detect_faces(img)
            print(f"🔍 检测到 {len(faces)} 个人脸")

            if len(faces) == 0:
                # 首次检测无结果时，尝试直方图均衡化增强图像后重试
                # 适用于光照不佳、对比度低的照片
                print("⚠️ 首次检测无结果，尝试图像增强...")
                gray_enhanced = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
                img_enhanced = cv2.cvtColor(gray_enhanced, cv2.COLOR_GRAY2BGR)
                faces = self.detect_faces(img_enhanced)
                print(f"🔍 增强后检测到 {len(faces)} 个人脸")

            if len(faces) == 0:
                print("❌ 图片中未检测到人脸（建议使用正面、光照均匀的照片）")
                return False

            # 保存人脸图片
            save_dir = os.path.join(self.face_db_path, name)
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, f"face_{len(faces)}.jpg")
            cv2.imencode(".jpg", img)[1].tofile(save_path)

            # 采集所有检测到的人脸特征
            all_features = [f["features"] for f in faces]

            # 存储特征列表和图片路径列表
            self.known_persons[name] = {
                "features": all_features,
                "image_paths": [save_path],
            }

            self._save_face_db()
            feat_dim = len(all_features[0])
            print(f"✅ 已注册: {name} (人脸数: {len(faces)}, 特征维度: {feat_dim})")
            return True

        except Exception as e:
            print(f"❌ 注册失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def add_face_to_person(self, name: str, image_bytes: bytes) -> bool:
        """
        对已有人员追加更多照片（提升识别置信度）

        功能:
            - 若人员不在人像库中，自动以注册方式入库
            - 兼容旧数据格式（单向量 → 列表，image_path → image_paths）
            - 追加新照片的特征向量到已有列表中

        参数:
            name: 人员姓名
            image_bytes: 新照片二进制数据

        返回:
            bool: 追加成功返回 True，失败返回 False
        """
        # 人员不在人像库中 → 自动注册
        # 兼容数据库有人像记录但面容库缺失的场景
        if name not in self.known_persons:
            print(f"⚠️ 人员 {name} 不在 face_db 中，自动注册")
            return self.register_face_from_bytes(name, image_bytes)

        # 兼容旧数据格式:
        # - features 从单向量转为列表
        # - image_path 重命名为 image_paths
        existing = self.known_persons[name]
        if "features" in existing and not isinstance(existing["features"], list):
            existing["features"] = [existing["features"]]
        if "image_path" in existing and "image_paths" not in existing:
            existing["image_paths"] = [existing["image_path"]]

        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                print("❌ 内存解码图片失败")
                return False

            print(f"📸 追加图片尺寸: {img.shape}")
            faces = self.detect_faces(img)
            print(f"🔍 检测到 {len(faces)} 个人脸")

            if len(faces) == 0:
                gray_enhanced = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
                img_enhanced = cv2.cvtColor(gray_enhanced, cv2.COLOR_GRAY2BGR)
                faces = self.detect_faces(img_enhanced)
                print(f"🔍 增强后检测到 {len(faces)} 个人脸")

            if len(faces) == 0:
                print("❌ 图片中未检测到人脸")
                return False

            # 保存新照片
            person_dir = os.path.join(self.face_db_path, name)
            os.makedirs(person_dir, exist_ok=True)
            idx = len(existing["image_paths"])
            save_path = os.path.join(person_dir, f"face_{idx + 1}.jpg")
            cv2.imencode(".jpg", img)[1].tofile(save_path)

            # 追加特征和路径
            existing["features"].extend([f["features"] for f in faces])
            existing["image_paths"].append(save_path)

            self._save_face_db()
            print(f"✅ 已追加: {name} (当前共 {len(existing['image_paths'])} 张照片, {len(existing['features'])} 个特征)")
            return True

        except Exception as e:
            print(f"❌ 追加失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def register_face(self, name: str, image_path: str) -> bool:
        """
        注册人脸到人像库（文件路径方式，与 register_face_from_bytes 兼容）

        参数:
            name: 人员姓名
            image_path: 图片文件路径

        返回:
            bool: 注册成功返回 True，失败返回 False

        注意:
            此方法使用 cv2.imread，不支持中文路径，
            建议优先使用 register_face_from_bytes
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                print(f"❌ 无法读取图片: {image_path}")
                return False

            print(f"📸 注册图片尺寸: {img.shape}")
            faces = self.detect_faces(img)
            print(f"🔍 检测到 {len(faces)} 个人脸")

            if len(faces) == 0:
                print("⚠️ 首次检测无结果，尝试图像增强...")
                gray_enhanced = cv2.equalizeHist(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
                img_enhanced = cv2.cvtColor(gray_enhanced, cv2.COLOR_GRAY2BGR)
                faces = self.detect_faces(img_enhanced)
                print(f"🔍 增强后检测到 {len(faces)} 个人脸")

            if len(faces) == 0:
                print(f"❌ 图片中未检测到人脸: {image_path}")
                return False

            save_dir = os.path.join(self.face_db_path, name)
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, "face_1.jpg")
            cv2.imwrite(save_path, img)

            all_features = [f["features"] for f in faces]
            self.known_persons[name] = {
                "features": all_features,
                "image_paths": [save_path],
            }

            self._save_face_db()
            print(f"✅ 已注册: {name} (人脸数: {len(faces)})")
            return True

        except Exception as e:
            print(f"❌ 注册失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def remove_face(self, name: str) -> bool:
        """
        从人像库中删除某人（同时清理照片文件和特征数据）

        参数:
            name: 人员姓名

        返回:
            bool: 始终返回 True

        删除内容:
            - known_persons 字典中的记录
            - 对应人员目录下的所有照片文件
            - 更新 pickle 持久化文件
        """
        import shutil
        if name in self.known_persons:
            del self.known_persons[name]
        # 清理照片文件夹
        person_dir = os.path.join(self.face_db_path, name)
        if os.path.isdir(person_dir):
            shutil.rmtree(person_dir, ignore_errors=True)
        self._save_face_db()
        return True

    # ==================== 人脸识别 ====================

    def recognize_faces(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        检测并识别画面中的所有人脸

        识别流程:
            1. 调用 detect_faces() 检测人脸并提取特征
            2. 遍历人像库，对每个已知人员计算余弦相似度
            3. 取每人所有特征向量中的最高相似度
            4. 筛选相似度 > 0.35 的匹配结果，按置信度降序排列

        参数:
            frame: BGR 格式的图像数组

        返回:
            List[Dict[str, Any]]: 识别结果列表，每项包含:
                - bbox: (x, y, w, h) 人脸边界框
                - score: float 检测置信度
                - is_unknown: bool 是否为未知人员
                - top_match: dict | None 最高置信度的匹配结果
                - all_matches: list 所有匹配结果（按置信度降序）

        阈值选择理由:
            0.35 作为最低阈值:
            - ArcFace 512 维特征的余弦相似度通常在 0.3~0.8 之间分布
            - < 0.35 通常为不同人，> 0.50 通常为同一人
            - 0.35 是一个偏宽松的阈值，优先保证召回率（减少漏检）
        """
        detected_faces = self.detect_faces(frame)

        results = []
        for face in detected_faces:
            x, y, bw, bh = face["bbox"]
            features = face["features"]

            # 与人像库比对 — 遍历每人所有特征向量，取最高余弦相似度
            # 多人像照片注册同一人时，多个特征向量可提高不同角度的识别精度
            matches = []
            for name, person_data in self.known_persons.items():
                known_features_list = person_data["features"]
                # 兼容旧数据: 单个特征向量转为列表
                if not isinstance(known_features_list, list) or isinstance(known_features_list, np.ndarray):
                    known_features_list = [known_features_list]

                best_similarity = 0.0
                for kf in known_features_list:
                    sim = self._cosine_similarity(features, kf)
                    if sim > best_similarity:
                        best_similarity = sim

                confidence = round(best_similarity * 100, 1)

                if best_similarity > 0.35:  # 识别阈值 0.35: 经验值，见模块文档说明
                    matches.append({
                        "name": name,
                        "confidence": confidence,
                        "similarity": round(best_similarity, 4),
                    })

            matches.sort(key=lambda x: x["confidence"], reverse=True)

            result = {
                "bbox": (x, y, bw, bh),
                "score": face["score"],
                "is_unknown": len(matches) == 0,
                "top_match": matches[0] if matches else None,
                "all_matches": matches,
            }
            results.append(result)

        return results

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """
        计算两个向量的余弦相似度

        公式: cos(θ) = (A·B) / (|A| × |B|)

        参数:
            a: 第一个特征向量
            b: 第二个特征向量

        返回:
            float: 相似度值 0.0~1.0（1.0 表示完全相同，0.0 表示正交）
                   零向量返回 0.0
        """
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    # ==================== 绘制结果 ====================

    def draw_results(
        self,
        frame: np.ndarray,
        results: List[Dict[str, Any]],
    ) -> np.ndarray:
        """
        在画面上绘制识别结果（人脸框 + 标签）

        颜色编码:
            - 绿色 (0, 255, 0): 高置信度匹配 (≥ 50%)
            - 黄色 (0, 255, 255): 中等置信度匹配 (< 50%)
            - 红色 (0, 0, 255): 未知人员

        参数:
            frame: BGR 格式的图像数组（将被原地修改）
            results: recognize_faces() 返回的识别结果列表

        返回:
            np.ndarray: 绘制了识别结果的图像（与输入为同一对象）
        """
        for r in results:
            x, y, bw, bh = r["bbox"]

            if r["is_unknown"]:
                color = (0, 0, 255)  # 红色 = 未知
                label = "未知"
            elif r["top_match"]["confidence"] >= 50:
                color = (0, 255, 0)  # 绿色 = 高置信度（ArcFace ≥ 0.5，通常为同一人）
                label = f"{r['top_match']['name']} ({r['top_match']['confidence']}%)"
            else:
                color = (0, 255, 255)  # 黄色 = 中等置信度（可能是同一人，但不够确定）
                label = f"{r['top_match']['name']}? ({r['top_match']['confidence']}%)"

            # 画框
            cv2.rectangle(frame, (x, y), (x + bw, y + bh), color, 2)
            # 画标签背景
            cv2.rectangle(frame, (x, y - 25), (x + bw, y), color, cv2.FILLED)
            cv2.putText(frame, label, (x + 6, y - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        return frame

    # ==================== 头像与统计 ====================

    def get_person_avatar(self, name: str) -> Optional[str]:
        """
        获取人员第一张注册照片的 base64 编码

        参数:
            name: 人员姓名

        返回:
            str | None: JPEG 图片的 base64 编码，人员不存在或文件缺失时返回 None

        实现说明:
            使用 numpy.fromfile + cv2.imdecode 读取，避免 cv2.imread 不支持中文路径
        """
        if name not in self.known_persons:
            return None
        paths = self.known_persons[name].get("image_paths", [])
        # 兼容旧数据
        if not paths:
            old_path = self.known_persons[name].get("image_path")
            if old_path and os.path.exists(old_path):
                paths = [old_path]
        if not paths or not os.path.exists(paths[0]):
            return None

        try:
            # 使用 numpy.fromfile + cv2.imdecode 读取，避免 cv2.imread 不支持中文路径
            img = cv2.imdecode(np.fromfile(paths[0], dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                return None
            _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
            return base64.b64encode(buf).decode("utf-8")
        except Exception:
            return None

    def get_photo_count(self, name: str) -> int:
        """
        获取某人的注册照片数量

        参数:
            name: 人员姓名

        返回:
            int: 照片数量，人员不存在时返回 0
        """
        if name not in self.known_persons:
            return 0
        paths = self.known_persons[name].get("image_paths", [])
        if not paths:
            old_path = self.known_persons[name].get("image_path")
            return 1 if old_path else 0
        return len(paths)

    # ==================== 工具方法 ====================

    @staticmethod
    def frame_to_base64(frame: np.ndarray) -> str:
        """
        将图像数组转为 base64 编码字符串

        参数:
            frame: BGR 格式的图像数组

        返回:
            str: JPEG 编码的 base64 字符串 (quality=80)
        """
        _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return base64.b64encode(buffer).decode("utf-8")

    @staticmethod
    def image_to_base64(image_path: str) -> str:
        """
        将图片文件转为 base64 编码字符串

        参数:
            image_path: 图片文件路径

        返回:
            str: 图片文件的 base64 编码字符串
        """
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")


# 全局单例 —— 供其他模块直接 import 使用，避免重复实例化
face_service = FaceService()
