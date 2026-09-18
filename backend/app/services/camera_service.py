"""
摄像头采集服务模块

核心职责:
    1. 管理多个摄像头流的生命周期（启动 / 停止 / 状态查询）
    2. 在独立守护线程中持续采集视频帧，并提供线程安全的最新帧缓存
    3. 支持帧回调机制，用于实时人脸检测等下游处理

支持的视频源:
    - 本地摄像头（USB / 内置）：source 填数字，如 "0"
    - RTSP 网络流：source 填 rtsp://... 地址
    - HTTP 视频流：source 填 http://... 地址（含 MJPEG / FFMPEG 后端自动尝试）

优化策略:
    - 帧缩放：统一缩放到 640px 宽度，大幅减少编码体积和后续检测计算量
    - JPEG 降质编码：quality=50，在画质与带宽之间取平衡
    - 帧跳过：每 3 帧才触发一次检测回调，降低 CPU 开销
    - 背压节流：检测回调最短间隔 1 秒，防止检测任务堆积
    - 场景变化检测：计算帧间差异，连续静态帧跳过检测，节省算力

依赖关系:
    - OpenCV (cv2): 视频采集与图像编解码
    - numpy: 帧间差异计算
    - threading: 多线程采集与线程安全锁
"""
import cv2
import threading
import time
import base64
from typing import Dict, Optional, Callable
from dataclasses import dataclass, field
import numpy as np


def _open_capture(*args, timeout=5.0):
    """
    打开 VideoCapture（带超时保护）

    功能:
        在独立线程中尝试打开视频源，防止 RTSP/HTTP 不通时阻塞主线程 30s+
        （OpenCV 默认超时很长，网络流不可达时会卡住）

    参数:
        *args: 传递给 cv2.VideoCapture 的参数（源地址、可选后端标识）
        timeout: 超时秒数，默认 5 秒

    返回:
        cv2.VideoCapture | None: 成功返回 VideoCapture 对象，超时或失败返回 None
    """
    result = {'cap': None, 'done': False}
    def _try():
        try:
            result['cap'] = cv2.VideoCapture(*args)
        except Exception:
            pass
        result['done'] = True
    t = threading.Thread(target=_try, daemon=True)
    t.start()
    t.join(timeout=timeout)
    return result['cap']


@dataclass
class CameraStream:
    """
    单个摄像头流（数据类 + 采集线程）

    核心职责:
        - 在独立守护线程中持续从视频源读取帧
        - 维护线程安全的最新帧缓存（base64 / JPEG 字节 / numpy 数组）
        - 提供帧回调接口，供下游（人脸检测）实时消费

    设计模式:
        - dataclass 简化字段声明，field(default_factory=...) 处理可变默认值
        - _lock (threading.Lock) 保证读写缓存的线程安全
        - 守护线程 (daemon=True) 随主进程退出自动结束

    背压机制说明:
        - _last_detect_submit: 记录上次提交检测的时间戳，最短间隔 1 秒
        - 当检测速度跟不上采集速度时，自动丢弃中间帧，避免检测任务堆积
        - skip_count: 每 3 帧才触发一次回调，进一步降低检测频率

    场景变化检测说明:
        - _last_detect_frame: 保存上次检测用的帧（numpy 数组）
        - 将当前帧与上次帧缩放到 64x64 后计算平均绝对差
        - 差异 < 5.0 视为静态画面，连续 10 帧静态后跳过检测，节省 CPU
        - 一旦画面发生变化，立即恢复检测
    """
    camera_id: str                              # 摄像头唯一标识
    source: str                                 # 视频源：数字=本地摄像头, rtsp/http=网络流
    name: str                                   # 摄像头显示名称
    location: str = ""                          # 摄像头安装位置描述
    fps: int = 15                               # 目标采集帧率
    rotation: int = 0                           # 画面旋转校正角度 0/90/180/270
    cap: Optional[cv2.VideoCapture] = None      # OpenCV VideoCapture 实例
    running: bool = False                       # 采集线程运行标志
    thread: Optional[threading.Thread] = None   # 采集线程引用
    on_frame: Optional[Callable] = None         # 帧回调: callback(camera_id, frame_ndarray, frame_b64)
    _lock: threading.Lock = field(default_factory=threading.Lock)   # 线程安全锁
    _latest_frame_b64: Optional[str] = None     # 最新帧 base64（供 HTTP API 返回）
    _latest_frame_jpg: Optional[bytes] = None   # 最新帧 JPEG 原始字节（供二进制 WebSocket 推送）
    _latest_result: Optional[dict] = None       # 最新检测结果（纯 dict，可 JSON 序列化）
    _latest_result_jpg: Optional[bytes] = None  # 检测结果 JPEG 字节（单独存储，不入 JSON）
    _last_detect_submit: float = 0              # 背压节流：上次提交检测的时间戳
    _last_detect_frame: Optional[np.ndarray] = None  # 场景变化检测：上次检测用的帧副本

    def start(self):
        """
        启动摄像头采集（多方式尝试打开，带超时保护）

        打开策略（依次尝试）:
            1. 默认方式：直接传入源地址，5 秒超时
            2. FFMPEG 后端：HTTP 流使用 cv2.CAP_FFMPEG 后端尝试
            3. MJPEG 后缀：HTTP 流追加 ?.mjpg 后缀尝试

        返回:
            bool: 启动成功返回 True，所有方式均失败返回 False
        """
        if self.source.isdigit():
            src = int(self.source)
        else:
            src = self.source

        opened = False

        # ---- 方式1：默认打开（带 5 秒超时保护）----
        # 适用于本地摄像头和标准 RTSP 流
        self.cap = _open_capture(src)
        if self.cap and self.cap.isOpened():
            opened = True

        # ---- 方式2：HTTP 流使用 FFMPEG 后端 ----
        # 部分 IP Camera 的 HTTP 流需要 FFMPEG 解码器才能正确打开
        if not opened and isinstance(src, str) and src.startswith('http'):
            if self.cap:
                self.cap.release()
            self.cap = _open_capture(src, cv2.CAP_FFMPEG)
            print(f"[{self.name}] 尝试 FFMPEG 后端...")
            if self.cap and self.cap.isOpened():
                opened = True

        # ---- 方式3：追加 MJPEG 后缀 ----
        # 部分 IP Camera 应用（如 DroidCam）需要在 URL 后加 .mjpg 才能获取 MJPEG 流
        if not opened and isinstance(src, str) and src.startswith('http') and '/video' in src:
            alt_src = src + '?.mjpg'
            if self.cap:
                self.cap.release()
            self.cap = _open_capture(alt_src)
            print(f"[{self.name}] 尝试 MJPEG 后缀: {alt_src}")
            if self.cap and self.cap.isOpened():
                opened = True

        if not opened:
            print(f"❌ 无法打开摄像头: {self.camera_id}")
            print(f"   视频源: {self.source}")
            print(f"   请确认: 1)手机IP Camera应用是否运行 2)IP地址端口是否可达 3)URL是否含/video")
            return False

        # 启动守护线程执行采集循环
        # daemon=True: 主进程退出时自动结束，不会阻塞程序退出
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        print(f"✅ 摄像头已启动: {self.name} ({self.camera_id})")
        return True

    def stop(self):
        """
        停止摄像头采集

        流程:
            1. 设置 running=False 通知采集线程退出循环
            2. 等待线程结束（最多 1 秒超时）
            3. 释放 VideoCapture 资源
            4. 清空所有缓存（帧 + 检测结果）
        """
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        if self.cap:
            self.cap.release()
        with self._lock:
            self._latest_frame_b64 = None
            self._latest_frame_jpg = None
            self._latest_result = None
            self._latest_result_jpg = None
            self._last_detect_frame = None
        print(f"摄像头已停止: {self.name}")

    def _capture_loop(self):
        """
        采集循环 — 在独立守护线程中持续运行

        帧处理流程:
            1. 从 VideoCapture 读取原始帧
            2. 按 FPS 间隔控制采集频率
            3. 缩放到 640px 宽度，减少编码体积和后续计算量
            4. JPEG 编码 (quality=50) + base64，供前端展示
            5. 每 3 帧 + 最短 1 秒间隔触发一次检测回调（背压机制）
            6. 场景变化检测：静态画面跳过检测，节省 CPU

        优化策略:
            - 缩放: 640px 宽度足以满足人脸检测需求，同时大幅减少数据量
            - JPEG quality=50: 在画质与带宽之间取平衡
            - 帧跳过 (skip_count): 每 3 帧触发一次检测，降低 CPU 开销
            - 背压节流 (_last_detect_submit): 最短 1 秒间隔，防止检测任务堆积
            - 场景变化检测: 缩放到 64x64 计算帧间差异，连续 10 帧静态则跳过
            - 旋转校正: 按需旋转检测帧，确保人脸检测方向正确
        """
        interval = 1.0 / max(self.fps, 1)  # 根据目标 FPS 计算最小采集间隔
        last_capture = 0                    # 上次采集的时间戳，用于帧率控制
        skip_count = 0                      # 帧跳过计数器：每 3 帧才触发人脸检测回调
        static_counter = 0                  # 连续静态帧计数：达到 10 帧无变化后强制检测一次

        while self.running:
            ret, frame = self.cap.read()
            if ret:
                now = time.time()
                if now - last_capture >= interval:
                    # ---- 缩放到 640px 宽度 ----
                    # 640px 足以满足人脸检测需求，同时大幅减少编码体积和后续计算量
                    h, w = frame.shape[:2]
                    if w > 640:
                        scale = 640.0 / w
                        frame_resized = cv2.resize(frame, (640, int(h * scale)))
                    else:
                        frame_resized = frame

                    # ---- JPEG 编码 + base64 ----
                    # quality=50: 在画质与带宽之间取平衡，前端预览足够清晰
                    _, buf = cv2.imencode(".jpg", frame_resized,
                                          [cv2.IMWRITE_JPEG_QUALITY, 50])
                    b64 = base64.b64encode(buf).decode("utf-8")
                    with self._lock:
                        self._latest_frame_b64 = b64
                        self._latest_frame_jpg = buf.tobytes()
                    last_capture = now

                    # ---- 帧跳过 + 背压节流 ----
                    # 每 3 帧 + 最短 1 秒间隔才触发一次检测回调:
                    #   - skip_count % 3: 降低检测频率，减少 CPU 开销
                    #   - now - _last_detect_submit >= 1.0: 背压机制，防止检测任务堆积
                    skip_count += 1
                    if self.on_frame and skip_count % 3 == 0 and now - self._last_detect_submit >= 1.0:
                        # ---- 按需旋转检测帧 ----
                        # 部分摄像头安装方向不同，需要旋转校正以确保人脸方向正确
                        if self.rotation in (90, 180, 270):
                            rotate_map = {90: cv2.ROTATE_90_CLOCKWISE,
                                          180: cv2.ROTATE_180,
                                          270: cv2.ROTATE_90_COUNTERCLOCKWISE}
                            detect_frame = cv2.rotate(frame_resized, rotate_map[self.rotation])
                        else:
                            detect_frame = frame_resized

                        # ---- 场景变化检测 ----
                        # 将当前帧与上次检测帧缩放到 64x64 后计算平均绝对差 (MAD)
                        # 64x64 极小图比较，计算开销极低（< 0.1ms）
                        # 差异阈值 5.0: 经验值，< 5 表示画面几乎无变化（如无人移动）
                        do_detect = True
                        if self._last_detect_frame is not None:
                            try:
                                # 计算帧间平均绝对差（缩放到 64x64 小图比较，极快 < 0.1ms）
                                cur_small = cv2.resize(detect_frame, (64, 64))
                                prev_small = cv2.resize(self._last_detect_frame, (64, 64))
                                diff = np.mean(np.abs(cur_small.astype(np.float32)
                                                      - prev_small.astype(np.float32)))
                                if diff < 5.0:     # 差异 < 5.0: 画面几乎无变化
                                    static_counter += 1
                                    if static_counter < 10:  # 连续 10 帧无变化才真正跳过（防止短暂静止导致漏检）
                                        do_detect = False
                                else:
                                    static_counter = 0
                            except Exception:
                                pass  # 比较失败则正常检测

                        if do_detect:
                            static_counter = 0
                            self._last_detect_submit = now
                            self._last_detect_frame = detect_frame.copy()
                            try:
                                # 传 numpy 数组（检测用）和 base64（展示用）
                                # 双格式传递：numpy 避免检测端重复 decode，base64 供前端直接使用
                                self.on_frame(self.camera_id, detect_frame, b64)
                            except Exception as e:
                                print(f"帧回调异常 [{self.camera_id}]: {e}")
            else:
                # 读帧失败时短暂休眠，避免空转消耗 CPU
                # 常见于网络流短暂中断或摄像头未就绪
                time.sleep(0.01)

    def get_latest_frame(self):
        """
        线程安全获取最新帧（解码为 numpy 数组）

        返回:
            np.ndarray | None: BGR 格式的图像数组，无可用帧时返回 None

        实现说明:
            从 base64 缓存解码，而非直接存储 numpy 数组，
            因为 base64 字符串比 numpy 数组占用内存更小，且 JPEG 压缩可大幅减少数据量
        """
        with self._lock:
            b64 = self._latest_frame_b64
        if b64 is None:
            return None
        buf = base64.b64decode(b64)
        nparr = np.frombuffer(buf, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    def get_latest_frame_b64(self):
        """
        线程安全获取最新帧的 base64 编码

        返回:
            str | None: JPEG 图片的 base64 编码字符串，无可用帧时返回 None
        """
        with self._lock:
            return self._latest_frame_b64

    def get_latest_frame_jpg(self):
        """
        线程安全获取最新帧的 JPEG 原始字节

        用途:
            直接通过二进制 WebSocket 推送给前端，避免重复编码

        返回:
            bytes | None: JPEG 编码的字节数据，无可用帧时返回 None
        """
        with self._lock:
            return self._latest_frame_jpg

    def get_latest_result(self):
        """
        获取最新检测结果（不含二进制数据，可安全 JSON 序列化）

        返回:
            dict | None: 检测结果字典的浅拷贝，无结果时返回 None

        实现说明:
            返回 dict() 浅拷贝，防止外部修改影响内部缓存
        """
        with self._lock:
            return dict(self._latest_result) if self._latest_result else None

    def get_latest_result_jpg(self):
        """
        获取最新检测结果的 JPEG 原始字节

        用途:
            用于二进制 WebSocket 推送，与 JSON 结果分离传输

        返回:
            bytes | None: 检测结果图片的 JPEG 字节，无结果时返回 None
        """
        with self._lock:
            return self._latest_result_jpg

    def set_latest_result(self, result: dict):
        """
        设置最新检测结果（线程安全）

        参数:
            result: 检测结果字典，将被浅拷贝存储
        """
        with self._lock:
            self._latest_result = dict(result)

    def set_latest_result_jpg(self, jpg_bytes: Optional[bytes]):
        """
        设置最新检测结果的 JPEG 字节（线程安全）

        参数:
            jpg_bytes: 检测结果图片的 JPEG 字节数据，传 None 表示清空
        """
        with self._lock:
            self._latest_result_jpg = jpg_bytes


class CameraManager:
    """
    摄像头管理器（多摄像头统一管理）

    核心职责:
        - 管理多个 CameraStream 实例的生命周期（添加 / 启动 / 停止）
        - 提供统一的帧获取和检测结果查询接口
        - 支持注册帧回调，用于实时人脸检测等下游处理

    设计模式:
        - 门面模式 (Facade): 将 CameraStream 的复杂操作封装为简洁的管理接口
        - 全局单例: 通过 camera_manager 全局实例访问

    使用方式:
        camera_manager.add_camera("cam_1", "0", "前门")
        camera_manager.start_camera("cam_1")
        frame = camera_manager.get_frame("cam_1")
    """

    def __init__(self):
        """初始化摄像头管理器，创建空的摄像头字典"""
        # cameras: {camera_id: CameraStream} — 所有已注册的摄像头
        self.cameras: Dict[str, CameraStream] = {}

    def add_camera(
        self,
        camera_id: str,
        source: str,
        name: str = "",
        location: str = "",
        fps: int = 15,
        rotation: int = 0,
    ) -> bool:
        """
        添加摄像头（仅注册，不启动）

        参数:
            camera_id: 摄像头唯一标识符
            source: 视频源地址（数字=本地，rtsp/http=网络流）
            name: 显示名称，默认为 camera_id
            location: 安装位置描述
            fps: 目标采集帧率，默认 15
            rotation: 画面旋转校正角度 (0/90/180/270)

        返回:
            bool: 注册成功返回 True，camera_id 已存在返回 False
        """
        if camera_id in self.cameras:
            return False

        camera = CameraStream(
            camera_id=camera_id,
            source=source,
            name=name or camera_id,
            location=location,
            fps=fps,
            rotation=rotation,
        )
        self.cameras[camera_id] = camera
        return True

    def start_camera(self, camera_id: str) -> bool:
        """
        启动指定摄像头的采集线程

        参数:
            camera_id: 摄像头唯一标识符

        返回:
            bool: 启动成功返回 True，摄像头不存在或启动失败返回 False
        """
        if camera_id not in self.cameras:
            return False
        return self.cameras[camera_id].start()

    def stop_camera(self, camera_id: str):
        """
        停止指定摄像头的采集线程并释放资源

        参数:
            camera_id: 摄像头唯一标识符
        """
        if camera_id in self.cameras:
            self.cameras[camera_id].stop()

    def stop_all(self):
        """停止所有摄像头的采集线程并释放资源（应用退出时调用）"""
        for camera in self.cameras.values():
            camera.stop()

    def get_frame(self, camera_id: str) -> Optional:
        """
        获取指定摄像头的最新帧（解码为 numpy 数组）

        实现说明:
            从缓存中读取，避免与采集线程竞争 VideoCapture

        参数:
            camera_id: 摄像头唯一标识符

        返回:
            np.ndarray | None: BGR 图像数组，摄像头不存在或无帧时返回 None
        """
        if camera_id not in self.cameras:
            return None
        return self.cameras[camera_id].get_latest_frame()

    def get_frame_b64(self, camera_id: str) -> Optional[str]:
        """
        获取指定摄像头最新帧的 base64 编码（供 HTTP API 返回）

        参数:
            camera_id: 摄像头唯一标识符

        返回:
            str | None: base64 编码字符串，摄像头不存在时返回 None
        """
        if camera_id not in self.cameras:
            return None
        return self.cameras[camera_id].get_latest_frame_b64()

    def get_frame_jpg(self, camera_id: str) -> Optional[bytes]:
        """
        获取指定摄像头最新帧的 JPEG 原始字节

        用途:
            用于二进制 WebSocket 推送，避免重复编码

        参数:
            camera_id: 摄像头唯一标识符

        返回:
            bytes | None: JPEG 字节数据，摄像头不存在时返回 None
        """
        if camera_id not in self.cameras:
            return None
        return self.cameras[camera_id].get_latest_frame_jpg()

    def get_last_result(self, camera_id: str) -> Optional[dict]:
        """
        获取指定摄像头的最新检测结果（JSON 可序列化）

        参数:
            camera_id: 摄像头唯一标识符

        返回:
            dict | None: 检测结果字典，摄像头不存在或无结果时返回 None
        """
        if camera_id not in self.cameras:
            return None
        return self.cameras[camera_id].get_latest_result()

    def get_result_jpg(self, camera_id: str) -> Optional[bytes]:
        """
        获取指定摄像头最新检测结果的 JPEG 原始字节

        用途:
            用于二进制 WebSocket 推送检测结果图片

        参数:
            camera_id: 摄像头唯一标识符

        返回:
            bytes | None: JPEG 字节数据，摄像头不存在时返回 None
        """
        if camera_id not in self.cameras:
            return None
        return self.cameras[camera_id].get_latest_result_jpg()

    def set_result_jpg(self, camera_id: str, jpg_bytes: Optional[bytes]):
        """
        设置指定摄像头最新检测结果的 JPEG 字节

        参数:
            camera_id: 摄像头唯一标识符
            jpg_bytes: 检测结果图片的 JPEG 字节，传 None 表示清空
        """
        if camera_id in self.cameras:
            self.cameras[camera_id].set_latest_result_jpg(jpg_bytes)

    def register_frame_callback(self, camera_id: str, callback: Callable):
        """
        注册帧回调函数（用于实时检测）

        回调签名:
            callback(camera_id: str, frame: np.ndarray, frame_b64: str) -> None

        参数:
            camera_id: 摄像头唯一标识符
            callback: 每触发一次检测时调用的回调函数
        """
        if camera_id in self.cameras:
            self.cameras[camera_id].on_frame = callback

    def set_last_result(self, camera_id: str, result: dict):
        """
        设置指定摄像头的最新检测结果

        参数:
            camera_id: 摄像头唯一标识符
            result: 检测结果字典
        """
        if camera_id in self.cameras:
            self.cameras[camera_id].set_latest_result(result)

    def get_status(self) -> Dict:
        """
        获取所有摄像头的运行状态（含最新检测结果）

        返回:
            Dict: {camera_id: {name, source, location, fps, rotation, running, latest_result}}
                  包含每个摄像头的基本信息和最新检测结果
        """
        return {
            cid: {
                "name": cam.name,
                "source": cam.source,
                "location": cam.location,
                "fps": cam.fps,
                "rotation": cam.rotation,
                "running": cam.running,
                "latest_result": cam.get_latest_result(),
            }
            for cid, cam in self.cameras.items()
        }


# 全局单例 —— 供其他模块直接 import 使用，避免重复实例化
camera_manager = CameraManager()
