"""
摄像头管理 API 模块 —— 摄像头的增删改查、视频流推送、人脸注册

包含的端点：
1. GET  /api/camera/list                    —— 获取所有摄像头状态
2. POST /api/camera/add                     —— 添加新摄像头
3. POST /api/camera/start/{camera_id}       —— 启动摄像头（含自动恢复）
4. POST /api/camera/stop/{camera_id}        —— 停止摄像头
5. DELETE /api/camera/{camera_id}           —— 删除摄像头
6. PUT  /api/camera/{camera_id}             —— 编辑摄像头配置
7. GET  /api/camera/snapshot/{camera_id}    —— 获取当前画面截图
8. WebSocket /api/camera/stream/{camera_id} —— 实时视频流（二进制 JPEG 推送）
9. POST /api/camera/register-face           —— 注册人脸（上传照片）
10. POST /api/camera/update-fps             —— 批量更新所有摄像头 FPS
11. POST /api/camera/update-rotation        —— 更新指定摄像头旋转角度
12. GET  /api/camera/database               —— 获取摄像头库完整数据

模块职责：
- 管理摄像头的完整生命周期（添加、启动、停止、删除、配置更新）
- 提供实时视频流推送（WebSocket 二进制协议，优化传输效率）
- 集成人脸识别：每帧异步检测 + 识别，结果缓存用于前端展示
- 支持人脸注册（通过上传照片方式）
"""
import json
import struct
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from backend.app.models.schemas import CameraInfo
from backend.app.services.camera_service import camera_manager
from backend.app.services.face_service import face_service
from backend.app.agents.vision_agent import vision_agent
from backend.app.agents.database_agent import db_agent
import asyncio
import base64
import numpy as np

# 路由前缀 /api/camera，标签为 camera（用于 Swagger 文档分组）
router = APIRouter(prefix="/api/camera", tags=["camera"])


@router.get("/list")
async def list_cameras():
    """
    获取所有摄像头状态

    HTTP方法: GET
    路径: /api/camera/list
    功能: 同时返回内存中的实时运行状态和数据库中的配置信息

    参数: 无

    返回值:
        online: 内存中摄像头的实时运行状态（来自 camera_manager）
        configured: 数据库中保存的摄像头配置列表（来自 db_agent）
    """
    # 获取内存中的摄像头实时运行状态
    cameras = camera_manager.get_status()
    # 获取数据库中保存的摄像头配置信息
    db_cameras = await db_agent.get_cameras()
    return {
        "online": cameras,
        "configured": db_cameras,
    }


@router.post("/add")
async def add_camera(camera: CameraInfo):
    """
    添加新摄像头

    HTTP方法: POST
    路径: /api/camera/add
    功能: 在内存和数据库中同时注册一个新摄像头

    参数:
        camera: CameraInfo 请求体，包含 id、name、source、location、fps、rotation

    返回值: {"message": "摄像头 xxx 已添加"}
    异常: 400 - 摄像头ID已存在
    """
    # 第一步：在内存中注册摄像头（camera_manager 负责管理运行时状态）
    success = camera_manager.add_camera(
        camera_id=camera.id,
        source=camera.source,
        name=camera.name,
        location=camera.location,
        fps=camera.fps,
        rotation=camera.rotation,
    )
    if not success:
        raise HTTPException(status_code=400, detail="摄像头ID已存在")

    # 第二步：持久化到数据库（确保重启后配置不丢失）
    await db_agent.add_camera({
        "id": camera.id,
        "name": camera.name,
        "source": camera.source,
        "location": camera.location,
        "fps": camera.fps,
        "rotation": camera.rotation,
    })

    return {"message": f"摄像头 {camera.name} 已添加"}


import time as _time
# 节流字典：记录每个摄像头上次执行人脸检测的时间戳，防止过于频繁的检测消耗资源
_last_detect_time: dict = {}  # 节流：每个摄像头最少间隔 0.6s


async def _process_frame(camera_id: str, detect_frame: np.ndarray, display_b64: str = None):
    """
    后台异步处理视频帧：人脸检测 + 识别（带节流机制）

    处理流程：
    1. 节流检查 —— 距上次检测不足 0.6 秒则跳过，避免 GPU/CPU 过载
    2. 调用 vision_agent 执行人脸检测和识别
    3. 生成展示帧（优先使用未旋转原帧，前端 CSS 旋转一次即可）
    4. 将检测结果（JPEG 字节 + 元数据）缓存到 camera_manager，供 WebSocket 推送使用

    参数:
        detect_frame: 旋转校正后的 numpy 帧（用于人脸检测，消除 base64 编解码往返）
        display_b64: 原始未旋转帧的 base64 编码（用于前端展示，避免 CSS 双重旋转）
    """
    # 节流检查：距上次检测不足 0.6 秒则跳过，避免过于频繁的人脸检测
    now = _time.time()
    if camera_id in _last_detect_time and now - _last_detect_time[camera_id] < 0.6:
        return  # 距上次检测不足 0.6 秒，跳过
    _last_detect_time[camera_id] = now

    try:
        # 调用视觉 Agent 执行人脸检测和识别
        result = await vision_agent.detect_and_recognize(detect_frame, camera_id, display_b64 or "")
        # 展示帧选择：优先使用未旋转原帧（前端 CSS 旋转一次），无原帧时降级使用带标注的检测帧
        show_b64 = display_b64 or result.get("annotated_frame", "")
        # 生成展示帧的 JPEG 原始字节（用于二进制 WebSocket 推送，避免 base64 体积膨胀）
        show_jpg = None
        if display_b64:
            show_jpg = base64.b64decode(display_b64)  # 已有 JPEG 字节，直接解码
        elif result.get("annotated_frame"):
            show_jpg = base64.b64decode(result["annotated_frame"])

        # 将 JPEG 字节缓存到 camera_manager，供视频流 WebSocket 推送
        camera_manager.set_result_jpg(camera_id, show_jpg)
        # 将检测结果元数据缓存到 camera_manager（人员数量、识别结果列表等）
        camera_manager.set_last_result(camera_id, {
            "image_base64": show_b64,
            "total_persons": result.get("total_persons", 0),     # 检测到的总人数
            "known_persons": result.get("known_persons", 0),     # 识别出的已知人员数
            "unknown_persons": result.get("unknown_persons", 0), # 未知人员数
            "persons": result.get("persons", []),                # 详细人员信息列表
        })
    except Exception as e:
        # 帧处理异常不应中断视频流，仅打印日志
        print(f"⚠️ 帧处理异常 [{camera_id}]: {e}")


@router.post("/start/{camera_id}")
async def start_camera(camera_id: str):
    """
    启动摄像头（自动从数据库恢复配置 + 注册实时检测回调）

    HTTP方法: POST
    路径: /api/camera/start/{camera_id}
    功能: 启动指定摄像头的视频流，自动注册人脸识别回调

    参数:
        camera_id: 摄像头唯一标识

    返回值: {"message": "摄像头 xxx 已启动"}
    异常:
        404 - 摄像头不存在（内存和数据库中均未找到）
        500 - 视频源打开失败（如 RTSP 地址不可达）

    执行流程：
    1. 检查内存中是否存在该摄像头，不存在则从数据库恢复配置
    2. 检查摄像头是否已在运行，避免重复启动
    3. 注册帧回调函数（每帧到来时异步触发人脸检测）
    4. 在线程池中启动摄像头（避免 cv2.VideoCapture 阻塞事件循环）
    """
    print(f"🔍 启动请求: {camera_id}, 内存中: {list(camera_manager.cameras.keys())}")

    # 第一步：内存中不存在 → 从数据库恢复配置
    if camera_id not in camera_manager.cameras:
        db_cams = await db_agent.get_cameras()
        found = next((c for c in db_cams if c["id"] == camera_id), None)
        if found:
            print(f"📦 从DB恢复: {found['name']}")
            camera_manager.add_camera(
                camera_id=found["id"],
                source=found["source"],
                name=found.get("name", found["id"]),
                location=found.get("location", ""),
                fps=found.get("fps", 15),
                rotation=found.get("rotation", 0),
            )
        else:
            raise HTTPException(status_code=404, detail=f"摄像头 {camera_id} 不存在")

    cam = camera_manager.cameras[camera_id]
    if cam.running:
        return {"message": f"摄像头 {camera_id} 已在运行"}

    # 第二步：注册实时检测回调
    # 获取当前事件循环，用于从同步回调线程中调度异步任务
    loop = asyncio.get_running_loop()

    def on_frame_callback(cid, detect_frame, display_b64=None):
        """
        帧回调函数（在摄像头采集线程中调用）

        使用 asyncio.run_coroutine_threadsafe 将异步人脸检测任务
        安全地调度到主事件循环中执行，实现跨线程的异步调用。
        """
        asyncio.run_coroutine_threadsafe(_process_frame(cid, detect_frame, display_b64), loop)

    camera_manager.register_frame_callback(camera_id, on_frame_callback)

    # 第三步：在线程池中启动摄像头
    # 关键：cv2.VideoCapture 是阻塞操作，必须在子线程执行，否则会阻塞 FastAPI 事件循环导致全局卡死
    started = await loop.run_in_executor(None, cam.start)
    if not started:
        raise HTTPException(
            status_code=500,
            detail=f"视频源打开失败: {cam.source}。请确认手机IP Webcam正在运行且视频源地址包含 /video 后缀",
        )

    print(f"✅ 已启动: {cam.name} ({camera_id})")
    return {"message": f"摄像头 {cam.name} 已启动"}


@router.post("/stop/{camera_id}")
async def stop_camera(camera_id: str):
    """
    停止摄像头

    HTTP方法: POST
    路径: /api/camera/stop/{camera_id}
    功能: 停止指定摄像头的视频流采集

    参数:
        camera_id: 摄像头唯一标识

    返回值: {"message": "摄像头 xxx 已停止"}
    """
    camera_manager.stop_camera(camera_id)
    return {"message": f"摄像头 {camera_id} 已停止"}


@router.delete("/{camera_id}")
async def delete_camera(camera_id: str):
    """
    删除摄像头（停止流 + 内存清理 + 数据库删除）

    HTTP方法: DELETE
    路径: /api/camera/{camera_id}
    功能: 完整移除摄像头，包括停止运行、释放内存、删除数据库记录

    参数:
        camera_id: 摄像头唯一标识

    返回值: {"message": "摄像头 xxx 已删除"}
    异常: 404 - 摄像头不存在

    执行流程：
    1. 如果摄像头正在运行，先停止视频流
    2. 从内存中移除摄像头实例
    3. 从数据库中删除摄像头配置记录
    """
    # 如果正在运行，先停止视频流
    camera_manager.stop_camera(camera_id)
    # 从内存中移除摄像头实例
    if camera_id in camera_manager.cameras:
        del camera_manager.cameras[camera_id]
    # 从数据库中删除配置记录
    success = await db_agent.delete_camera(camera_id)
    if not success:
        raise HTTPException(status_code=404, detail="摄像头不存在")
    return {"message": f"摄像头 {camera_id} 已删除"}


@router.put("/{camera_id}")
async def update_camera(camera_id: str, camera: CameraInfo):
    """
    编辑摄像头配置

    HTTP方法: PUT
    路径: /api/camera/{camera_id}
    功能: 更新摄像头的配置信息（名称、视频源、位置、帧率、旋转角度），同步更新数据库和内存

    参数:
        camera_id: 摄像头唯一标识（路径参数）
        camera: CameraInfo 请求体，包含更新后的配置

    返回值: {"message": "摄像头 xxx 已更新"}
    异常: 404 - 摄像头不存在
    """
    # 第一步：更新数据库中的配置
    success = await db_agent.update_camera(camera_id, {
        "name": camera.name,
        "source": camera.source,
        "location": camera.location,
        "fps": camera.fps,
        "rotation": camera.rotation,
    })
    if not success:
        raise HTTPException(status_code=404, detail="摄像头不存在")
    # 第二步：同步更新内存中的 CameraStream 实例（使配置立即生效，无需重启）
    if camera_id in camera_manager.cameras:
        cam = camera_manager.cameras[camera_id]
        cam.name = camera.name
        cam.source = camera.source
        cam.location = camera.location
        cam.fps = camera.fps
        cam.rotation = camera.rotation
    return {"message": f"摄像头 {camera.name} 已更新"}


@router.get("/snapshot/{camera_id}")
async def get_snapshot(camera_id: str):
    """
    获取摄像头当前画面（优先取缓存检测结果，避免重复计算）

    HTTP方法: GET
    路径: /api/camera/snapshot/{camera_id}
    功能: 返回当前帧的检测结果（含标注框、识别信息等）

    参数:
        camera_id: 摄像头唯一标识

    返回值: 包含 image_base64（标注后的画面）、total_persons、persons 等字段
    异常: 404 - 摄像头不可用或尚未产生画面

    策略：
    - 优先返回实时检测缓存（_process_frame 产生的结果），避免重复检测
    - 降级方案：缓存不存在时，使用当前帧调用 vision_agent 做单次检测
    """
    # 优先返回实时检测缓存（由 _process_frame 持续生成）
    cached = camera_manager.get_last_result(camera_id)
    if cached and cached.get("image_base64"):
        return {
            "camera_id": camera_id,
            **cached,
        }

    # 降级方案：获取当前缓存帧，手动执行一次检测
    frame_b64 = camera_manager.get_frame_b64(camera_id)
    if frame_b64 is None:
        raise HTTPException(status_code=404, detail="摄像头不可用或尚未产生画面")

    result = await vision_agent.detect_and_recognize(frame_b64, camera_id)

    return {
        "camera_id": camera_id,
        "image_base64": result.get("annotated_frame", frame_b64),
        **{k: v for k, v in result.items() if k != "annotated_frame"},
    }


@router.websocket("/stream/{camera_id}")
async def camera_stream(websocket: WebSocket, camera_id: str):
    """
    WebSocket 实时视频流（二进制 JPEG 推送，消除 base64 开销）

    HTTP方法: WebSocket
    路径: /api/camera/stream/{camera_id}
    功能: 持续推送摄像头的实时画面帧，优先使用二进制协议提升传输效率

    参数:
        camera_id: 摄像头唯一标识

    二进制帧格式:
        [4字节元数据长度(uint32 大端)] [元数据JSON] [JPEG字节]
        - 元数据包含 total_persons 和 persons 识别结果
        - JPEG 为标注后的画面帧

    JSON 帧格式（降级方案）:
        {"type": "frame", "image_base64": "...", "total_persons": N, "persons": [...]}

    推送策略（优先级从高到低）：
    1. 缓存检测结果（二进制 JPEG） —— 最高效，含人脸标注
    2. 缓存检测结果（JSON base64） —— 降级兼容
    3. 原始帧（二进制 JPEG） —— 无检测结果时推送原始画面
    4. 原始帧（JSON base64） —— 最终降级方案

    客户端控制消息:
        {"type": "stop"} —— 停止视频流推送
    """
    await websocket.accept()

    # 如果摄像头已注册但未启动，异步尝试启动（不阻塞 WebSocket 连接建立）
    if camera_id in camera_manager.cameras and not camera_manager.cameras[camera_id].running:
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, camera_manager.start_camera, camera_id)

    try:
        while True:
            # 尝试接收客户端控制消息（非阻塞，超时 0.1 秒）
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                msg = json.loads(data)
                if msg.get("type") == "stop":
                    break  # 客户端请求停止视频流
            except asyncio.TimeoutError:
                pass  # 超时表示客户端没有控制消息，继续推送帧

            # 优先推送缓存检测结果（二进制 JPEG，最高效）
            cached = camera_manager.get_last_result(camera_id)
            cached_jpg = camera_manager.get_result_jpg(camera_id)
            if cached and cached_jpg:
                # 二进制推送：消除 base64 编码开销和 JSON 体积膨胀
                meta = json.dumps({
                    "total_persons": cached.get("total_persons", 0),
                    "persons": cached.get("persons", []),
                }).encode("utf-8")
                # 使用 struct.pack 打包为 4 字节大端整数（元数据长度前缀）
                header = struct.pack("!I", len(meta))
                await websocket.send_bytes(header + meta + cached_jpg)
            elif cached and cached.get("image_base64"):
                # 降级方案1：文本 JSON 推送（兼容 snapshot API 场景）
                await websocket.send_json({
                    "type": "frame",
                    "image_base64": cached["image_base64"],
                    "total_persons": cached.get("total_persons", 0),
                    "persons": cached.get("persons", []),
                })
            else:
                # 无缓存检测结果：推送原始帧
                jpg_bytes = camera_manager.get_frame_jpg(camera_id)
                if jpg_bytes is not None:
                    # 降级方案2：原始帧二进制推送
                    meta = json.dumps({"total_persons": 0, "persons": []}).encode("utf-8")
                    header = struct.pack("!I", len(meta))
                    await websocket.send_bytes(header + meta + jpg_bytes)
                else:
                    # 降级方案3：原始帧 base64 JSON 推送
                    frame_b64 = camera_manager.get_frame_b64(camera_id)
                    if frame_b64 is not None:
                        await websocket.send_json({
                            "type": "frame",
                            "image_base64": frame_b64,
                            "total_persons": 0,
                            "persons": [],
                        })

            # 控制推送帧率：15 FPS（每帧间隔约 66ms）
            await asyncio.sleep(1.0 / 15)  # 15 FPS

    except WebSocketDisconnect:
        pass  # 客户端断开连接，正常退出
    except Exception as e:
        print(f"❌ 视频流错误: {e}")


@router.post("/register-face")
async def register_face(
    name: str,
    file: UploadFile = File(...),
):
    """
    注册人脸（通过上传照片方式）

    HTTP方法: POST
    路径: /api/camera/register-face
    功能: 上传一张包含人脸的照片，提取特征并注册到人脸库

    参数:
        name: 人员姓名（表单字段）
        file: 上传的照片文件

    返回值: {"message": "✅ xxx 已成功注册"}
    异常: 400 - 人脸注册失败（照片中无清晰正面人脸）

    执行流程：
    1. 将上传文件保存到 data/uploads/ 目录
    2. 调用 face_service 从图片字节中提取人脸特征并注册
    3. 将人员信息同步写入数据库
    """
    import aiofiles
    import os

    # 计算绝对路径，避免工作目录不一致导致文件存储错误
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    upload_dir = os.path.join(base_dir, "data", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    # 读取上传文件内容并保存到磁盘
    content = await file.read()
    file_path = os.path.join(upload_dir, f"{name}_{file.filename}")
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    # 调用 face_service 注册人脸
    # 使用 bytes 内存解码方式（OpenCV 不支持中文路径，避免路径编码问题）
    success = face_service.register_face_from_bytes(name, content)
    if not success:
        raise HTTPException(status_code=400, detail="人脸注册失败，请确保照片中有清晰正面人脸")

    # 将人员信息同步写入数据库（face_encoding_path 和 face_image_path 指向 face_db 目录）
    from backend.app.models.schemas import PersonInfo
    await db_agent.add_person(PersonInfo(
        name=name,
        face_encoding_path=f"./data/face_db/{name}/",
        face_image_path=f"./data/face_db/{name}/face.jpg",
    ))

    return {"message": f"✅ {name} 已成功注册"}


@router.post("/update-fps")
async def update_all_fps(fps: int = 15):
    """
    批量更新所有摄像头的 FPS（帧率）

    HTTP方法: POST
    路径: /api/camera/update-fps
    功能: 一次性更新数据库中所有摄像头的帧率设置，并同步更新内存中的实例

    参数:
        fps: 目标帧率，默认 15

    返回值: {"message": "所有摄像头 FPS 已更新为 xx"}
    """
    from backend.app.models.database import async_session, CameraInfoModel
    from sqlalchemy import select, update

    # 批量更新数据库中所有摄像头的 fps 字段
    async with async_session() as session:
        await session.execute(
            update(CameraInfoModel).values(fps=fps)
        )
        await session.commit()

    # 同步更新内存中正在运行的摄像头实例（立即生效，无需重启）
    for cam in camera_manager.cameras.values():
        cam.fps = fps

    return {"message": f"所有摄像头 FPS 已更新为 {fps}"}


@router.post("/update-rotation")
async def update_rotation(camera_id: str, rotation: int = 0):
    """
    更新指定摄像头的画面旋转角度

    HTTP方法: POST
    路径: /api/camera/update-rotation
    功能: 设置摄像头画面的旋转角度（用于校正倒置/侧置的摄像头画面）

    参数:
        camera_id: 摄像头唯一标识
        rotation: 旋转角度，必须是 0/90/180/270 之一

    返回值: {"message": "摄像头 xxx 旋转角已更新为 xx°（已立即生效/启动后生效）"}
    异常: 400 - rotation 参数不合法
    """
    # 参数校验：仅允许 0、90、180、270 四个值
    if rotation not in (0, 90, 180, 270):
        raise HTTPException(status_code=400, detail="rotation 必须是 0/90/180/270")

    from backend.app.models.database import async_session, CameraInfoModel
    from sqlalchemy import select, update

    # 更新数据库中的旋转角度配置
    async with async_session() as session:
        await session.execute(
            update(CameraInfoModel)
            .where(CameraInfoModel.id == camera_id)
            .values(rotation=rotation)
        )
        await session.commit()

    # 同步更新内存中的摄像头实例（如果已启动则立即生效，否则启动后生效）
    if camera_id in camera_manager.cameras:
        camera_manager.cameras[camera_id].rotation = rotation
        return {"message": f"摄像头 {camera_id} 旋转角已更新为 {rotation}°（已立即生效）"}

    return {"message": f"摄像头 {camera_id} 旋转角已保存为 {rotation}°（启动后生效）"}


@router.get("/database")
async def get_camera_database():
    """
    获取摄像头库完整数据（含分辨率、IP、运行时长等详细信息）

    HTTP方法: GET
    路径: /api/camera/database
    功能: 聚合数据库配置和实时运行状态，返回前端摄像头库表格所需的完整数据

    参数: 无

    返回值:
        cameras: 摄像头详细信息列表（含 id、name、source、location、fps、status、resolution、ip、last_online、uptime）
        total: 摄像头总数
    """
    # 获取数据库中的摄像头配置
    db_cameras = await db_agent.get_cameras()
    # 获取内存中的实时运行状态
    online_status = camera_manager.get_status()

    # 聚合数据库配置和实时状态，构建前端所需的完整数据
    result = []
    for cam in db_cameras:
        online = online_status.get(cam["id"], {})
        result.append({
            "id": cam["id"],                                            # 摄像头ID
            "name": cam.get("name", cam["id"]),                         # 摄像头名称
            "source": cam.get("source", ""),                            # 视频源地址
            "location": cam.get("location", ""),                        # 安装位置
            "fps": cam.get("fps", 5),                                   # 帧率
            "status": "在线" if online.get("running") else "离线",      # 运行状态（中文）
            "resolution": online.get("resolution", "1920×1080"),        # 分辨率
            "ip": _extract_ip(cam.get("source", "")),                   # 从视频源中提取 IP 地址
            "last_online": online.get("last_frame_time", "--"),         # 最后在线时间
            "uptime": online.get("uptime", "--"),                       # 运行时长
        })

    return {"cameras": result, "total": len(result)}


def _extract_ip(source: str) -> str:
    """
    从 RTSP 视频源地址中提取 IP 地址

    使用正则表达式匹配 IPv4 地址，如果未匹配到则返回原始 source 字符串。

    参数:
        source: 视频源地址（如 "rtsp://192.168.1.100:554/stream"）

    返回值: 提取的 IP 地址字符串（如 "192.168.1.100"），或原始 source
    """
    import re
    match = re.search(r'(\d+\.\d+\.\d+\.\d+)', source)
    return match.group(1) if match else source
"""
摄像头管理 API
"""
import json
import struct
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from backend.app.models.schemas import CameraInfo
from backend.app.services.camera_service import camera_manager
from backend.app.services.face_service import face_service
from backend.app.agents.vision_agent import vision_agent
from backend.app.agents.database_agent import db_agent
import asyncio
import base64
import numpy as np

router = APIRouter(prefix="/api/camera", tags=["camera"])


@router.get("/list")
async def list_cameras():
    """获取所有摄像头状态（含在线检测结果）"""
    cameras = camera_manager.get_status()
    db_cameras = await db_agent.get_cameras()
    return {
        "online": cameras,
        "configured": db_cameras,
    }


@router.post("/add")
async def add_camera(camera: CameraInfo):
    """添加摄像头"""
    success = camera_manager.add_camera(
        camera_id=camera.id,
        source=camera.source,
        name=camera.name,
        location=camera.location,
        fps=camera.fps,
        rotation=camera.rotation,
    )
    if not success:
        raise HTTPException(status_code=400, detail="摄像头ID已存在")

    # 保存到数据库
    await db_agent.add_camera({
        "id": camera.id,
        "name": camera.name,
        "source": camera.source,
        "location": camera.location,
        "fps": camera.fps,
        "rotation": camera.rotation,
    })

    return {"message": f"摄像头 {camera.name} 已添加"}


import time as _time
_last_detect_time: dict = {}  # 节流：每个摄像头最少间隔 0.3s


async def _process_frame(camera_id: str, detect_frame: np.ndarray, display_b64: str = None):
    """后台异步处理帧：人脸检测+识别（带节流），结果缓存到摄像头实例
    detect_frame: 旋转校正后的 numpy 帧（消除 base64 编解码往返）
    display_b64: 原始未旋转帧 base64（用于前端展示，避免 CSS 双重旋转）
    """
    now = _time.time()
    if camera_id in _last_detect_time and now - _last_detect_time[camera_id] < 0.6:
        return  # 距上次检测不足 0.3 秒，跳过
    _last_detect_time[camera_id] = now

    try:
        result = await vision_agent.detect_and_recognize(detect_frame, camera_id, display_b64 or "")
        # 展示用未旋转原帧，前端 CSS 旋一次即可；无原帧时降级用标注帧
        show_b64 = display_b64 or result.get("annotated_frame", "")
        # 同时生成展示帧的 JPEG 原始字节（给二进制 WebSocket 推送用）
        show_jpg = None
        if display_b64:
            show_jpg = base64.b64decode(display_b64)  # 已有 JPEG，直接解码
        elif result.get("annotated_frame"):
            show_jpg = base64.b64decode(result["annotated_frame"])

        camera_manager.set_result_jpg(camera_id, show_jpg)
        camera_manager.set_last_result(camera_id, {
            "image_base64": show_b64,
            "total_persons": result.get("total_persons", 0),
            "known_persons": result.get("known_persons", 0),
            "unknown_persons": result.get("unknown_persons", 0),
            "persons": result.get("persons", []),
        })
    except Exception as e:
        print(f"⚠️ 帧处理异常 [{camera_id}]: {e}")


@router.post("/start/{camera_id}")
async def start_camera(camera_id: str):
    """启动摄像头（自动从DB恢复 + 注册实时检测回调）"""
    print(f"🔍 启动请求: {camera_id}, 内存中: {list(camera_manager.cameras.keys())}")

    # 内存中不存在 → 从数据库恢复
    if camera_id not in camera_manager.cameras:
        db_cams = await db_agent.get_cameras()
        found = next((c for c in db_cams if c["id"] == camera_id), None)
        if found:
            print(f"📦 从DB恢复: {found['name']}")
            camera_manager.add_camera(
                camera_id=found["id"],
                source=found["source"],
                name=found.get("name", found["id"]),
                location=found.get("location", ""),
                fps=found.get("fps", 15),
                rotation=found.get("rotation", 0),
            )
        else:
            raise HTTPException(status_code=404, detail=f"摄像头 {camera_id} 不存在")

    cam = camera_manager.cameras[camera_id]
    if cam.running:
        return {"message": f"摄像头 {camera_id} 已在运行"}

    # 注册实时检测回调：每帧线程安全地调度异步人脸识别
    loop = asyncio.get_running_loop()

    def on_frame_callback(cid, detect_frame, display_b64=None):
        asyncio.run_coroutine_threadsafe(_process_frame(cid, detect_frame, display_b64), loop)

    camera_manager.register_frame_callback(camera_id, on_frame_callback)

    # 关键：start() 含 cv2.VideoCapture，必须在子线程执行，否则阻塞事件循环致全局卡死
    started = await loop.run_in_executor(None, cam.start)
    if not started:
        raise HTTPException(
            status_code=500,
            detail=f"视频源打开失败: {cam.source}。请确认手机IP Webcam正在运行且视频源地址包含 /video 后缀",
        )

    print(f"✅ 已启动: {cam.name} ({camera_id})")
    return {"message": f"摄像头 {cam.name} 已启动"}


@router.post("/stop/{camera_id}")
async def stop_camera(camera_id: str):
    """停止摄像头"""
    camera_manager.stop_camera(camera_id)
    return {"message": f"摄像头 {camera_id} 已停止"}


@router.delete("/{camera_id}")
async def delete_camera(camera_id: str):
    """删除摄像头（停止流 + 内存清理 + 数据库删除）"""
    # 如果正在运行，先停止
    camera_manager.stop_camera(camera_id)
    # 从内存移除
    if camera_id in camera_manager.cameras:
        del camera_manager.cameras[camera_id]
    # 从数据库删除
    success = await db_agent.delete_camera(camera_id)
    if not success:
        raise HTTPException(status_code=404, detail="摄像头不存在")
    return {"message": f"摄像头 {camera_id} 已删除"}


@router.put("/{camera_id}")
async def update_camera(camera_id: str, camera: CameraInfo):
    """编辑摄像头配置"""
    success = await db_agent.update_camera(camera_id, {
        "name": camera.name,
        "source": camera.source,
        "location": camera.location,
        "fps": camera.fps,
        "rotation": camera.rotation,
    })
    if not success:
        raise HTTPException(status_code=404, detail="摄像头不存在")
    # 同步更新内存中的 CameraStream
    if camera_id in camera_manager.cameras:
        cam = camera_manager.cameras[camera_id]
        cam.name = camera.name
        cam.source = camera.source
        cam.location = camera.location
        cam.fps = camera.fps
        cam.rotation = camera.rotation
    return {"message": f"摄像头 {camera.name} 已更新"}


@router.get("/snapshot/{camera_id}")
async def get_snapshot(camera_id: str):
    """获取摄像头当前画面（优先取缓存检测结果，避免重复计算）"""
    # 优先返回实时检测缓存
    cached = camera_manager.get_last_result(camera_id)
    if cached and cached.get("image_base64"):
        return {
            "camera_id": camera_id,
            **cached,
        }

    # 降级：用缓存帧做检测
    frame_b64 = camera_manager.get_frame_b64(camera_id)
    if frame_b64 is None:
        raise HTTPException(status_code=404, detail="摄像头不可用或尚未产生画面")

    result = await vision_agent.detect_and_recognize(frame_b64, camera_id)

    return {
        "camera_id": camera_id,
        "image_base64": result.get("annotated_frame", frame_b64),
        **{k: v for k, v in result.items() if k != "annotated_frame"},
    }


@router.websocket("/stream/{camera_id}")
async def camera_stream(websocket: WebSocket, camera_id: str):
    """
    WebSocket 实时视频流（二进制 JPEG 推送，消除 base64 开销）
    二进制帧格式: [4字节元数据长度(uint32 BE)] [元数据JSON] [JPEG字节]
    """
    await websocket.accept()

    # 如果摄像头未启动，尝试启动（异步执行，不阻塞 WebSocket）
    if camera_id in camera_manager.cameras and not camera_manager.cameras[camera_id].running:
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, camera_manager.start_camera, camera_id)

    try:
        while True:
            # 接收客户端控制消息
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                msg = json.loads(data)
                if msg.get("type") == "stop":
                    break
            except asyncio.TimeoutError:
                pass

            # 优先推送缓存检测结果
            cached = camera_manager.get_last_result(camera_id)
            cached_jpg = camera_manager.get_result_jpg(camera_id)
            if cached and cached_jpg:
                # 二进制推送：消除 base64 编码开销和 JSON 体积膨胀
                meta = json.dumps({
                    "total_persons": cached.get("total_persons", 0),
                    "persons": cached.get("persons", []),
                }).encode("utf-8")
                header = struct.pack("!I", len(meta))
                await websocket.send_bytes(header + meta + cached_jpg)
            elif cached and cached.get("image_base64"):
                # 降级：文本 JSON（兼容 snapshot API 场景）
                await websocket.send_json({
                    "type": "frame",
                    "image_base64": cached["image_base64"],
                    "total_persons": cached.get("total_persons", 0),
                    "persons": cached.get("persons", []),
                })
            else:
                # 无缓存结果：推送原始帧（二进制优先）
                jpg_bytes = camera_manager.get_frame_jpg(camera_id)
                if jpg_bytes is not None:
                    meta = json.dumps({"total_persons": 0, "persons": []}).encode("utf-8")
                    header = struct.pack("!I", len(meta))
                    await websocket.send_bytes(header + meta + jpg_bytes)
                else:
                    frame_b64 = camera_manager.get_frame_b64(camera_id)
                    if frame_b64 is not None:
                        await websocket.send_json({
                            "type": "frame",
                            "image_base64": frame_b64,
                            "total_persons": 0,
                            "persons": [],
                        })

            await asyncio.sleep(1.0 / 15)  # 15 FPS

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"❌ 视频流错误: {e}")


@router.post("/register-face")
async def register_face(
    name: str,
    file: UploadFile = File(...),
):
    """注册人脸（上传照片）"""
    import aiofiles
    import os

    # 用绝对路径避免工作目录不一致的问题
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    upload_dir = os.path.join(base_dir, "data", "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    content = await file.read()
    file_path = os.path.join(upload_dir, f"{name}_{file.filename}")
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    # OpenCV 不支持中文路径，直接传 bytes 内存解码
    success = face_service.register_face_from_bytes(name, content)
    if not success:
        raise HTTPException(status_code=400, detail="人脸注册失败，请确保照片中有清晰正面人脸")

    # 同步保存到数据库
    from backend.app.models.schemas import PersonInfo
    await db_agent.add_person(PersonInfo(
        name=name,
        face_encoding_path=f"./data/face_db/{name}/",
        face_image_path=f"./data/face_db/{name}/face.jpg",
    ))

    return {"message": f"✅ {name} 已成功注册"}


@router.post("/update-fps")
async def update_all_fps(fps: int = 15):
    """批量更新所有摄像头的 FPS"""
    from backend.app.models.database import async_session, CameraInfoModel
    from sqlalchemy import select, update

    async with async_session() as session:
        await session.execute(
            update(CameraInfoModel).values(fps=fps)
        )
        await session.commit()

    # 同时更新内存中的摄像头
    for cam in camera_manager.cameras.values():
        cam.fps = fps

    return {"message": f"所有摄像头 FPS 已更新为 {fps}"}


@router.post("/update-rotation")
async def update_rotation(camera_id: str, rotation: int = 0):
    """更新指定摄像头的画面旋转角度（0/90/180/270）"""
    if rotation not in (0, 90, 180, 270):
        raise HTTPException(status_code=400, detail="rotation 必须是 0/90/180/270")

    from backend.app.models.database import async_session, CameraInfoModel
    from sqlalchemy import select, update

    async with async_session() as session:
        await session.execute(
            update(CameraInfoModel)
            .where(CameraInfoModel.id == camera_id)
            .values(rotation=rotation)
        )
        await session.commit()

    # 同时更新内存中的摄像头（如果已启动，需重启后生效）
    if camera_id in camera_manager.cameras:
        camera_manager.cameras[camera_id].rotation = rotation
        return {"message": f"摄像头 {camera_id} 旋转角已更新为 {rotation}°（已立即生效）"}

    return {"message": f"摄像头 {camera_id} 旋转角已保存为 {rotation}°（启动后生效）"}


@router.get("/database")
async def get_camera_database():
    """
    获取摄像头库完整数据（含分辨率、IP、运行时长等详细信息）
    用于前端摄像头库表格展示
    """
    db_cameras = await db_agent.get_cameras()
    online_status = camera_manager.get_status()

    result = []
    for cam in db_cameras:
        online = online_status.get(cam["id"], {})
        result.append({
            "id": cam["id"],
            "name": cam.get("name", cam["id"]),
            "source": cam.get("source", ""),
            "location": cam.get("location", ""),
            "fps": cam.get("fps", 5),
            "status": "在线" if online.get("running") else "离线",
            "resolution": online.get("resolution", "1920×1080"),
            "ip": _extract_ip(cam.get("source", "")),
            "last_online": online.get("last_frame_time", "--"),
            "uptime": online.get("uptime", "--"),
        })

    return {"cameras": result, "total": len(result)}


def _extract_ip(source: str) -> str:
    """从RTSP源提取IP地址"""
    import re
    match = re.search(r'(\d+\.\d+\.\d+\.\d+)', source)
    return match.group(1) if match else source
