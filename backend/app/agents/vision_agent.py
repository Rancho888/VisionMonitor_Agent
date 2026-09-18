"""
视觉 Agent（Vision Agent）- 负责人脸检测和识别

模块职责：
    1. 对监控画面进行人脸检测（基于 InsightFace SCRFD 模型）
    2. 对检测到的人脸进行识别（基于 ArcFace 特征向量 + FAISS 检索）
    3. 自动将识别结果写入数据库（带 5 秒去重机制）
    4. 支持调用 LLM 进行深度画面分析（复杂场景理解）
    5. 支持调用 LLM 辅助人脸比对（处理困难样本）

架构说明：
    - 人脸检测/识别在线程池中执行，避免阻塞 asyncio 事件循环
    - 每路摄像头独立执行，支持最多 4 路并发
    - 识别结果自动保存截图和数据库记录
"""
import asyncio
import concurrent.futures
import numpy as np
from typing import Dict, Any, Optional, Union
from datetime import datetime
from backend.app.services.face_service import face_service
from backend.app.services.llm_service import llm_service
from backend.app.agents.database_agent import db_agent
from backend.app.models.schemas import FaceRecord

# 去重机制：同一人名在 _DEDUP_SECONDS 秒内只保存一次数据库记录，
# 避免同一人连续多帧出现时写入大量重复记录
_PERSON_COOLDOWN: Dict[str, datetime] = {}
_DEDUP_SECONDS = 5.0
# 线程池执行器：每路摄像头独立执行，max_workers=4 支持 4 路并发处理
# 使用 ThreadPoolExecutor 而非 ProcessPoolExecutor，因为 InsightFace 模型已包含 C++ 优化
_DETECT_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4)


class VisionAgent:
    """
    视觉分析 Agent，封装人脸检测、识别、LLM 分析等能力。

    核心方法：
        - detect_and_recognize: 本地人脸检测+识别（线程池异步）
        - analyze_scene_with_llm: 调用多模态 LLM 深度分析画面场景
        - compare_with_llm: 调用 LLM 辅助人脸比对
    """

    async def detect_and_recognize(
        self, frame_input: Union[np.ndarray, str], camera_id: str = "",
        snapshot_b64: str = ""
    ) -> Dict[str, Any]:
        """
        检测并识别画面中的人脸。

        支持两种输入格式：
            - numpy 数组（优化路径，直接处理，无需编解码）
            - base64 字符串（兼容旧 API，内部转为 numpy 数组）

        处理流程：
            1. 解析输入并缩放到 640 宽度（平衡精度与速度）
            2. 在线程池中执行人脸检测+识别（避免阻塞事件循环）
            3. 绘制标注框并整理结果
            4. 自动保存截图和数据库记录（带 5 秒去重）

        Args:
            frame_input: 画面数据，numpy 数组或 base64 编码字符串
            camera_id: 摄像头 ID，用于记录来源，空字符串时不保存记录
            snapshot_b64: 原始画面 base64，用于保存识别记录截图

        Returns:
            dict，包含：
            - total_persons: 检测到的总人数（int）
            - known_persons: 已知人员数（int）
            - unknown_persons: 未知人员数（int）
            - persons: 人员详情列表（每项含 name, confidence, is_unknown 等）
            - annotated_frame: 标注后的画面 base64 字符串
        """
        import cv2
        import base64

        # 根据输入类型解析帧数据
        if isinstance(frame_input, np.ndarray):
            # 直接传入的 numpy 数组，无需编解码（优化路径）
            frame = frame_input
        else:
            # 兼容旧接口：base64 字符串输入，需解码为 numpy 数组
            img_bytes = base64.b64decode(frame_input)
            nparr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # 将画面缩放到 640 宽度，保持宽高比
        # 目的：平衡检测精度与处理速度，原图过大时 InsightFace 会较慢
        if frame is not None:
            h, w = frame.shape[:2]
            if w > 640:
                scale = 640.0 / w
                frame = cv2.resize(frame, (640, int(h * scale)))

        # 帧数据无效时返回空结果
        if frame is None:
            return {
                "total_persons": 0,
                "known_persons": 0,
                "unknown_persons": 0,
                "persons": [],
                "annotated_frame": "",
            }

        # 在线程池中执行人脸检测和识别，避免阻塞 asyncio 事件循环
        # 使用 run_in_executor 将同步的 CPU 密集操作移到后台线程
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(_DETECT_EXECUTOR, face_service.recognize_faces, frame)
        # 绘制检测结果标注框（使用 frame.copy() 避免修改原始帧）
        annotated_frame = await loop.run_in_executor(
            _DETECT_EXECUTOR, face_service.draw_results, frame.copy(), results)

        # 整理检测结果为结构化字典
        persons = []
        for r in results:
            # 提取最佳匹配结果（top_match 为置信度最高的人员）
            person = {
                "is_unknown": r["is_unknown"],
                "name": r["top_match"]["name"] if r["top_match"] else "未知",
                "confidence": r["top_match"]["confidence"] if r["top_match"] else 0,
                "detection_score": round(r["score"], 2),
            }
            # 若存在其他候选人（多张人脸特征相似度较高），附加次优匹配
            if not r["is_unknown"] and len(r["all_matches"]) > 1:
                person["other_matches"] = r["all_matches"][1:]
            persons.append(person)

        # 自动写入识别记录到数据库（带 5 秒去重：同一人名不重复保存）
        # 仅当指定了 camera_id 且检测到人员时才保存
        if camera_id and persons:
            now = datetime.now()
            # 保存当前帧截图到文件（所有识别记录共用同一帧截图）
            snap_path = ""
            if snapshot_b64:
                try:
                    import os as _os
                    snap_dir = "data/snapshots"
                    _os.makedirs(snap_dir, exist_ok=True)
                    snap_file = f"{snap_dir}/{camera_id}_{now.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
                    with open(snap_file, "wb") as f:
                        f.write(base64.b64decode(snapshot_b64))
                    snap_path = snap_file
                except Exception as e:
                    print(f"保存截图失败: {e}")
            for p in persons:
                # 去重 key：已知人员用姓名，陌生人统一用 __unknown__
                # 这样避免同一陌生人多张脸刷屏，已知人员则按姓名去重
                dedup_key = p["name"] if not p["is_unknown"] else "__unknown__"
                # 在冷却时间内则跳过，避免同一人连续帧重复写入
                last = _PERSON_COOLDOWN.get(dedup_key)
                if last and (now - last).total_seconds() < _DEDUP_SECONDS:
                    continue
                _PERSON_COOLDOWN[dedup_key] = now  # 更新最后保存时间
                try:
                    # 保存识别记录到数据库
                    await db_agent.save_face_record(FaceRecord(
                        camera_id=camera_id,
                        person_name=p["name"],
                        confidence=p["confidence"],
                        is_unknown=p["is_unknown"],
                        detected_at=now,
                        snapshot_path=snap_path,
                    ))
                except Exception as e:
                    print(f"保存记录失败: {e}")

        # 返回结构化结果：包含人员统计和标注后的画面
        return {
            "known_persons": sum(1 for p in persons if not p["is_unknown"]),
            "unknown_persons": sum(1 for p in persons if p["is_unknown"]),
            "persons": persons,
            "annotated_frame": face_service.frame_to_base64(annotated_frame),
        }

    async def analyze_scene_with_llm(self, frame_base64: str, question: str = "") -> str:
        """
        使用多模态大模型分析画面（深度理解场景）。

        适用场景：回答用户关于画面的复杂问题，如"这个人正在做什么"、
        "画面中有哪些异常"等需要深度理解的问题。

        Args:
            frame_base64: 画面的 base64 编码字符串
            question: 用户的具体问题，默认为通用的场景描述提示

        Returns:
            LLM 生成的画面分析文本
        """
        # 无特定问题时使用通用的场景描述提示
        prompt = question or "请详细描述画面中的场景，包括：有哪些人、在做什么、环境信息等。"
        return await llm_service.analyze_image(frame_base64, prompt)

    async def compare_with_llm(
        self,
        monitor_frame_base64: str,
        reference_image_base64: str,
        reference_name: str,
    ) -> Dict[str, Any]:
        """
        使用多模态大模型进行人脸比对（辅助手段，处理困难样本）。

        当本地人脸特征向量相似度处于边界区间时，可调用此方法
        让 LLM 从视觉角度辅助判断是否为同一人。

        Args:
            monitor_frame_base64: 监控画面的 base64 编码
            reference_image_base64: 参考照片的 base64 编码
            reference_name: 参考照片对应的人员姓名

        Returns:
            dict，包含 LLM 的比对结果和置信度判断
        """
        return await llm_service.compare_faces(
            monitor_frame_base64,
            reference_image_base64,
            reference_name,
        )


# 全局单例：供 monitor_tools 和 API 层调用
vision_agent = VisionAgent()
