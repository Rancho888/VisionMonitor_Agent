"""
识别记录 API 模块 —— 历史记录查询、分页、统计聚合、截图获取

包含的端点：
1. GET    /api/records                  —— 分页查询识别记录（支持多条件筛选）
2. GET    /api/records/summary          —— 获取今日 + 总览统计卡片
3. DELETE /api/records/clear            —— 清空全部识别记录
4. GET    /api/records/snapshot/{id}    —— 获取指定记录的截图（base64）

模块职责：
- 提供人脸识别记录的分页查询和多维度筛选（姓名、摄像头、时间范围、人员类型）
- 聚合统计数据（今日识别数、已知/未知人员数、活跃摄像头数等）
- 提供截图文件的读取和 base64 编码服务
"""
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse
from datetime import datetime, timedelta
import base64
import os
from backend.app.agents.database_agent import db_agent

# 路由前缀 /api/records，标签为 records（用于 Swagger 文档分组）
router = APIRouter(prefix="/api/records", tags=["records"])


@router.get("")
async def list_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    person_name: str = Query("", description="按姓名筛选"),
    camera_id: str = Query("", description="按摄像头筛选"),
    start_time: str = Query("", description="开始时间 ISO 格式"),
    end_time: str = Query("", description="结束时间 ISO 格式"),
    record_type: str = Query("", description="类型: known / unknown / 空=全部"),
):
    """
    分页查询识别记录（支持多条件组合筛选）

    HTTP方法: GET
    路径: /api/records
    功能: 根据筛选条件分页查询人脸检测记录，支持按人员姓名、摄像头、时间范围、人员类型过滤

    参数:
        page: 当前页码（从 1 开始，默认 1）
        page_size: 每页记录数（1~100，默认 20）
        person_name: 按识别人员姓名筛选（空字符串=不筛选）
        camera_id: 按来源摄像头ID筛选（空字符串=不筛选）
        start_time: 开始时间，ISO 格式（如 "2026-06-01T00:00:00"）
        end_time: 结束时间，ISO 格式
        record_type: 记录类型筛选 —— "known"=仅已知人员, "unknown"=仅未知人员, ""=全部

    返回值:
        records: 当前页的记录列表
        total: 满足条件的总记录数
        page: 当前页码
        page_size: 每页大小
        total_pages: 总页数
    """
    # 解析时间参数：将 ISO 格式字符串转为 datetime 对象，空字符串则不筛选
    st = datetime.fromisoformat(start_time) if start_time else None
    et = datetime.fromisoformat(end_time) if end_time else None
    # 清理姓名和摄像头参数的空白字符，空字符串转为 None（表示不筛选）
    pn = person_name.strip() or None
    cid = camera_id.strip() or None

    # 根据 record_type 确定 is_unknown 筛选值
    is_unknown = None
    if record_type == "known":
        is_unknown = False      # 仅查询已知人员
    elif record_type == "unknown":
        is_unknown = True       # 仅查询未知人员

    # 第一步：查询满足条件的总记录数（用于计算总页数）
    total = await db_agent.count_records(
        person_name=pn, camera_id=cid,
        start_time=st, end_time=et, is_unknown=is_unknown,
    )

    # 第二步：计算分页偏移量并查询当前页数据
    offset = (page - 1) * page_size
    records = await db_agent.query_records(
        person_name=pn, camera_id=cid,
        start_time=st, end_time=et, is_unknown=is_unknown,
        limit=page_size, offset=offset,
    )

    return {
        "records": records,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size) if total > 0 else 1,
    }


@router.get("/summary")
async def records_summary():
    """
    获取今日 + 总览统计卡片

    HTTP方法: GET
    路径: /api/records/summary
    功能: 聚合计算多个统计指标，用于前端仪表盘展示

    参数: 无

    返回值:
        today_total: 今日总识别次数
        today_known: 今日已知人员识别次数
        today_unknown: 今日未知人员识别次数
        yesterday_total: 昨日总识别次数
        total_all: 历史总识别次数
        active_cameras: 今日活跃摄像头数（今天有产生识别记录的摄像头数量）
    """
    now = datetime.now()
    # 计算今日起止时间（精确到秒的微秒归零）
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)

    # 今日统计：总次数、已知人员次数、未知人员次数
    today_total = await db_agent.count_records(start_time=today_start)
    today_known = await db_agent.count_records(start_time=today_start, is_unknown=False)
    today_unknown = await db_agent.count_records(start_time=today_start, is_unknown=True)
    # 昨日统计：昨日起止时间内的总识别次数
    yesterday_total = await db_agent.count_records(
        start_time=yesterday_start, end_time=today_start,
    )
    # 历史总识别次数
    total_all = await db_agent.count_records()

    # 活跃摄像头数：统计今天有产生识别记录的不同摄像头数量（去重计数）
    from backend.app.models.database import async_session, FaceRecordModel
    from sqlalchemy import select, func, and_
    async with async_session() as session:
        q = select(func.count(func.distinct(FaceRecordModel.camera_id))).where(
            FaceRecordModel.detected_at >= today_start
        )
        r = await session.execute(q)
        active_cams = r.scalar() or 0

    return {
        "today_total": today_total,
        "today_known": today_known,
        "today_unknown": today_unknown,
        "yesterday_total": yesterday_total,
        "total_all": total_all,
        "active_cameras": active_cams,
    }


@router.delete("/clear")
async def clear_all_records():
    """
    清空全部识别记录

    HTTP方法: DELETE
    路径: /api/records/clear
    功能: 删除数据库中所有的人脸识别记录（不可恢复）

    参数: 无

    返回值: {"message": "已清空 N 条识别记录", "deleted": N}
    """
    count = await db_agent.clear_all_records()
    return {"message": f"已清空 {count} 条识别记录", "deleted": count}


@router.get("/snapshot/{record_id}")
async def get_snapshot(record_id: int):
    """
    获取识别记录的截图（base64 编码）

    HTTP方法: GET
    路径: /api/records/snapshot/{record_id}
    功能: 根据记录ID查询对应的监控截图，读取磁盘文件并以 base64 编码返回

    参数:
        record_id: 识别记录的数据库ID

    返回值: {"record_id": N, "snapshot_base64": "...base64编码的图片数据..."}
    异常:
        404 - 该记录无截图 / 截图文件不存在

    执行流程：
    1. 从数据库查询记录，获取截图文件路径
    2. 校验截图文件是否存在于磁盘
    3. 读取文件字节并 base64 编码返回
    """
    # 第一步：从数据库查询记录信息
    record = await db_agent.get_record_by_id(record_id)
    if not record or not record.get("snapshot_path"):
        raise HTTPException(status_code=404, detail="该记录无截图或不存在")
    # 第二步：校验截图文件是否存在于磁盘
    snap_path = record["snapshot_path"]
    if not os.path.exists(snap_path):
        raise HTTPException(status_code=404, detail="截图文件不存在")
    # 第三步：读取文件并 base64 编码
    with open(snap_path, "rb") as f:
        img_bytes = f.read()
    return {
        "record_id": record_id,
        "snapshot_base64": base64.b64encode(img_bytes).decode("utf-8"),
    }
"""
识别记录 API — 历史查询、分页、统计
"""
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse
from datetime import datetime, timedelta
import base64
import os
from backend.app.agents.database_agent import db_agent

router = APIRouter(prefix="/api/records", tags=["records"])


@router.get("")
async def list_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    person_name: str = Query("", description="按姓名筛选"),
    camera_id: str = Query("", description="按摄像头筛选"),
    start_time: str = Query("", description="开始时间 ISO 格式"),
    end_time: str = Query("", description="结束时间 ISO 格式"),
    record_type: str = Query("", description="类型: known / unknown / 空=全部"),
):
    """分页查询识别记录"""
    st = datetime.fromisoformat(start_time) if start_time else None
    et = datetime.fromisoformat(end_time) if end_time else None
    pn = person_name.strip() or None
    cid = camera_id.strip() or None

    is_unknown = None
    if record_type == "known":
        is_unknown = False
    elif record_type == "unknown":
        is_unknown = True

    total = await db_agent.count_records(
        person_name=pn, camera_id=cid,
        start_time=st, end_time=et, is_unknown=is_unknown,
    )

    offset = (page - 1) * page_size
    records = await db_agent.query_records(
        person_name=pn, camera_id=cid,
        start_time=st, end_time=et, is_unknown=is_unknown,
        limit=page_size, offset=offset,
    )

    return {
        "records": records,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size) if total > 0 else 1,
    }


@router.get("/summary")
async def records_summary():
    """获取今日 + 总览统计卡片"""
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)

    today_total = await db_agent.count_records(start_time=today_start)
    today_known = await db_agent.count_records(start_time=today_start, is_unknown=False)
    today_unknown = await db_agent.count_records(start_time=today_start, is_unknown=True)
    yesterday_total = await db_agent.count_records(
        start_time=yesterday_start, end_time=today_start,
    )
    total_all = await db_agent.count_records()

    # 活跃摄像头数（今天有记录的摄像头）
    from backend.app.models.database import async_session, FaceRecordModel
    from sqlalchemy import select, func, and_
    async with async_session() as session:
        q = select(func.count(func.distinct(FaceRecordModel.camera_id))).where(
            FaceRecordModel.detected_at >= today_start
        )
        r = await session.execute(q)
        active_cams = r.scalar() or 0

    return {
        "today_total": today_total,
        "today_known": today_known,
        "today_unknown": today_unknown,
        "yesterday_total": yesterday_total,
        "total_all": total_all,
        "active_cameras": active_cams,
    }


@router.delete("/clear")
async def clear_all_records():
    """清空全部识别记录"""
    count = await db_agent.clear_all_records()
    return {"message": f"已清空 {count} 条识别记录", "deleted": count}


@router.get("/snapshot/{record_id}")
async def get_snapshot(record_id: int):
    """获取识别记录的截图（base64）"""
    record = await db_agent.get_record_by_id(record_id)
    if not record or not record.get("snapshot_path"):
        raise HTTPException(status_code=404, detail="该记录无截图或不存在")
    snap_path = record["snapshot_path"]
    if not os.path.exists(snap_path):
        raise HTTPException(status_code=404, detail="截图文件不存在")
    with open(snap_path, "rb") as f:
        img_bytes = f.read()
    return {
        "record_id": record_id,
        "snapshot_base64": base64.b64encode(img_bytes).decode("utf-8"),
    }
