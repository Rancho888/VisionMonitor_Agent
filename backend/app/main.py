"""
Vision Monitor Agent - 主入口
智能监控助手后端服务
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# .env 在 backend/ 目录下（DOCKER 模式由 docker-compose env_file 注入环境变量，
# load_dotenv 找不到文件会静默跳过；本地开发时从项目根目录运行可正确加载）
load_dotenv(dotenv_path="backend/.env")

from backend.app.models.database import init_db
from backend.app.api.chat import router as chat_router
from backend.app.api.camera import router as camera_router
from backend.app.api.preview import router as preview_router
from backend.app.api.person import router as person_router
from backend.app.api.records import router as records_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动时
    print("=" * 50)
    print("🚀 Vision Monitor Agent 启动中...")
    await init_db()
    print("✅ 数据库初始化完成")

    # 从 pickle 恢复到数据库（若 person_info 为空但 pickle 有数据）
    try:
        from backend.app.services.face_service import face_service
        from backend.app.agents.database_agent import db_agent as _db_agent
        db_persons = await _db_agent.get_all_persons()
        if not db_persons and face_service.known_persons:
            print(f"⚠️ person_info 为空，but pickle 有 {len(face_service.known_persons)} 人，正在恢复...")
            from backend.app.models.schemas import PersonInfo
            for p in face_service.get_persons_for_recovery():
                try:
                    pi = PersonInfo(
                        name=p["name"],
                        face_image_path=p["face_image_path"],
                        face_encoding_path=p["face_encoding_path"],
                        category=p.get("category", "staff"),
                        department=p.get("department", ""),
                    )
                    await _db_agent.add_person(pi)
                    print(f"  ✅ 恢复人员: {p['name']}")
                except Exception as ex:
                    print(f"  ⚠️ 恢复 {p['name']} 失败: {ex}")
            print(f"✅ 人像库恢复完成")
    except Exception as ex:
        print(f"⚠️ 人像库恢复跳过: {ex}")

    # 从数据库恢复摄像头配置
    from backend.app.services.camera_service import camera_manager
    from backend.app.agents.database_agent import db_agent
    saved_cameras = await db_agent.get_cameras()
    for cam in saved_cameras:
        camera_manager.add_camera(
            camera_id=cam["id"],
            source=cam["source"],
            name=cam.get("name", cam["id"]),
            location=cam.get("location", ""),
            fps=cam.get("fps", 15),
        )
    print(f"📷 已加载 {len(saved_cameras)} 个摄像头")

    # 预热 InsightFace 模型（首次推理慢，提前跑一次避免冷启动）
    try:
        from backend.app.agents.vision_agent import vision_agent
        import numpy as np, cv2, base64
        dummy = np.zeros((640, 480, 3), dtype=np.uint8)
        _, buf = cv2.imencode(".jpg", dummy)
        dummy_b64 = base64.b64encode(buf).decode("utf-8")
        await vision_agent.detect_and_recognize(dummy_b64, "")
        print("✅ InsightFace 模型预热完成")
    except Exception as e:
        print(f"⚠️ 模型预热跳过: {e}")

    print(f"API 文档: http://localhost:{os.getenv('PORT', '8000')}/docs")
    print("=" * 50)
    yield
    # 关闭时
    from backend.app.services.camera_service import camera_manager
    camera_manager.stop_all()
    print("🛑 服务已关闭")


app = FastAPI(
    title="Vision Monitor Agent",
    description="智能监控助手 - 多Agent协作的视觉监控对话系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置（允许前端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat_router)
app.include_router(camera_router)
app.include_router(preview_router)
app.include_router(person_router)
app.include_router(records_router)


@app.get("/")
async def root():
    return {
        "name": "Vision Monitor Agent",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=False,  # 关闭热重载，防止程序修改文件时被回退
    )
