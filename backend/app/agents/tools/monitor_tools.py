"""
监控 Tools - LangChain @tool 装饰的工具函数模块

模块职责：
    定义所有可供 LLM Agent 调用的监控工具函数。
    每个工具的 docstring 是 LLM 判断何时调用的核心依据，
    必须清晰描述功能、参数、返回内容和使用场景。

工具列表：
    - realtime_check: 实时检测当前监控画面中的人员
    - history_query: 查询人脸识别历史记录
    - statistics: 查询高频人员排名与统计数据
    - person_manage: 管理注册人员信息库
    - alert_rules: 查看告警规则配置
    - camera_status: 查看摄像头配置和运行状态

工具间关系：
    - realtime_check 和 history_query 可组合使用：先看实时画面，再查历史
    - statistics 和 history_query 可组合使用：先看统计排名，再查具体某人
    - camera_status 和 realtime_check 可组合使用：先看摄像头状态，再查看具体画面
"""
import json
from typing import Optional
from datetime import datetime, timedelta
from langchain_core.tools import tool

from backend.app.agents.database_agent import db_agent
from backend.app.agents.vision_agent import vision_agent
from backend.app.services.camera_service import camera_manager
from backend.app.services.face_service import face_service


# ==================== 实时查看 ====================
# 用于检测当前监控画面中的人员，调用 vision_agent 进行人脸检测和识别

@tool
async def realtime_check(camera_id: Optional[str] = None) -> str:
    """
    查看当前监控画面的实时情况：检测画面中有哪些人、是否认识、有多少人。

    适用场景（正例）:
    - 用户问"现在谁在"、"看看监控"、"实时情况"、"当前画面"
    - 用户想了解某个摄像头的当前画面
    - 用户问"现在有人吗"、"谁在办公室"

    不适用场景（反例）:
    - 问过去的情况（用 history_query）
    - 问统计排名（用 statistics）
    - 纯闲聊，不涉及实时画面

    Args:
        camera_id: 可选，指定摄像头 ID；不传则检查所有已启动的摄像头。
            类型为字符串或 None，无取值范围限制。

    Returns:
        JSON 字符串，结构如下：
        - type: "realtime"
        - camera_count: 检查的摄像头数量（int）
        - cameras: 各摄像头的检测结果 dict，每个包含：
            - name: 摄像头名称
            - total_persons: 总人数
            - known_persons: 已知人员数
            - unknown_persons: 未知人员数
            - persons: 人员详情列表（name, confidence, is_unknown）
        若无摄像头：status="no_camera", message 提示用户启动摄像头
    """
    # 获取所有摄像头的运行状态
    cameras = camera_manager.get_status()
    # 若指定了有效 camera_id 则只检查该摄像头，否则检查全部
    target_ids = [camera_id] if camera_id and camera_id in cameras else list(cameras.keys())

    results = {}
    for cid in target_ids:
        # 从摄像头服务获取当前帧（numpy 数组，None 表示无画面）
        frame = camera_manager.get_frame(cid)
        if frame is None:
            results[cid] = {
                "name": cameras.get(cid, {}).get("name", cid),
                "status": "无画面（摄像头未启动或无信号）",
            }
            continue
        try:
            # 将帧转为 base64，调用 vision_agent 进行人脸检测+识别
            frame_b64 = face_service.frame_to_base64(frame)
            analysis = await vision_agent.detect_and_recognize(frame_b64, cid)
            cam_info = cameras.get(cid, {})
            results[cid] = {
                "name": cam_info.get("name", cid),
                "location": cam_info.get("location", ""),
                "total_persons": analysis.get("total_persons", 0),
                "known_persons": analysis.get("known_persons", 0),
                "unknown_persons": analysis.get("unknown_persons", 0),
                "persons": analysis.get("persons", []),
            }
        except Exception as e:
            results[cid] = {
                "name": cameras.get(cid, {}).get("name", cid),
                "error": str(e),
            }

    # 无可用摄像头时返回提示信息
    if not results:
        return json.dumps({
            "status": "no_camera",
            "message": "当前没有可用的摄像头。请先通过前端界面添加并启动摄像头。",
        }, ensure_ascii=False)

    # 返回结构化结果供 LLM 解读
    return json.dumps({
        "type": "realtime",
        "camera_count": len(results),
        "cameras": results,
    }, ensure_ascii=False, indent=2)


# ==================== 历史查询 ====================
# 用于查询人脸识别历史记录，支持按人员、时间范围筛选

@tool
async def history_query(
    person_name: Optional[str] = None,
    time_range: str = "最近7天",
    limit: int = 20,
) -> str:
    """
    查询人脸识别历史记录：某人什么时候出现过、出现了几次。

    适用场景（正例）:
    - 用户问"张三最近来过吗"、"今天谁来了"、"看看历史记录"
    - 查询特定人员的历史出现记录
    - 查询某个时间段内的所有人员记录

    不适用场景（反例）:
    - 问当前实时画面（用 realtime_check）
    - 问统计排名/高频人员（用 statistics）

    工具组合建议：
    - 可先调用 realtime_check 看实时画面，再用本工具查历史
    - 可先调用 statistics 看排名，再用本工具查具体某人的详情

    Args:
        person_name: 可选，要查询的人员姓名（字符串）。
            不传则查全部人员记录。
        time_range: 时间范围（字符串），仅支持以下固定值：
            "今天" | "昨天" | "本周" | "本月" | "最近7天"。
            其他值将默认回退为"最近7天"。
        limit: 返回记录数量上限（int），默认 20，建议不超过 50。

    Returns:
        JSON 字符串，结构如下：
        - type: "history"
        - person_name: 查询的人员名（null 表示全部）
        - time_range: 时间范围
        - record_count: 匹配的记录数（int）
        - records: 记录列表，每条包含 id, camera_id, person_name,
            confidence, snapshot_path, detected_at, is_unknown
        - stats: 若查特定人员，包含该人的统计信息（total_appearances,
            days_active, daily_breakdown, last_seen）；查全部时为 null
    """
    # 解析时间范围：将中文时间范围字符串映射为具体的 datetime 起点
    now = datetime.now()
    time_map = {
        "今天": now.replace(hour=0, minute=0, second=0),
        "昨天": (now - timedelta(days=1)).replace(hour=0, minute=0, second=0),
        "本周": (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0),
        "本月": now.replace(day=1, hour=0, minute=0, second=0),
        "最近7天": now - timedelta(days=7),
    }
    # 未匹配到的时间范围默认回退为最近 7 天
    start_time = time_map.get(time_range, now - timedelta(days=7))

    # 查询匹配的记录列表
    records = await db_agent.query_records(
        person_name=person_name,
        start_time=start_time,
        limit=limit,
    )

    # 若查询特定人员，额外获取该人员的统计摘要
    stats = None
    if person_name:
        stats = await db_agent.get_person_stats(person_name)

    return json.dumps({
        "type": "history",
        "person_name": person_name,
        "time_range": time_range,
        "record_count": len(records),
        "records": records[:20],
        "stats": stats,
    }, ensure_ascii=False, indent=2, default=str)


# ==================== 统计分析 ====================
# 用于查询监控统计数据，包括高频人员排名和注册人员总数

@tool
async def statistics(days: int = 7) -> str:
    """
    查询监控统计数据：高频出现的人员排名、注册人员总数。

    适用场景（正例）:
    - 用户问"最近一周谁来得最多"、"统计一下"、"排名"
    - 用户想了解整体出现频率趋势
    - 用户问"这个月谁最活跃"

    不适用场景（反例）:
    - 查询某人的具体历史记录（用 history_query）
    - 查询实时画面（用 realtime_check）

    工具组合建议：
    - 可先调用本工具看排名，再用 history_query 查具体某人的详细记录

    Args:
        days: 统计天数（int），默认 7 天。取值范围 1-365。

    Returns:
        JSON 字符串，结构如下：
        - type: "statistics"
        - days: 统计天数（int）
        - top_persons: 高频人员列表，每项包含 name（姓名）和 count（出现次数）
        - total_registered: 注册人员总数（int）
    """
    # 获取 Top 10 高频出现人员（排除陌生人）
    top_persons = await db_agent.get_top_persons(days=days, limit=10)
    # 获取所有注册人员列表，用于统计总数
    all_persons = await db_agent.get_all_persons()

    return json.dumps({
        "type": "statistics",
        "days": days,
        "top_persons": top_persons,
        "total_registered": len(all_persons),
    }, ensure_ascii=False, indent=2)


# ==================== 人员管理 ====================
# 用于查看和管理注册人员信息库，支持列表查看和删除操作

@tool
async def person_manage(action: str, name: Optional[str] = None) -> str:
    """
    管理人员信息库：查看列表、删除人员。

    适用场景（正例）:
    - 用户问"有哪些注册人员"、"人员列表"、"人员库"
    - 用户说"删除XXX"、"移除XXX的人员信息"

    不适用场景（反例）:
    - 查询某人的出现历史（用 history_query）
    - 查看实时画面中的人（用 realtime_check）
    - 添加新人员（需通过前端上传接口）

    Args:
        action: 操作类型（字符串，必填），仅支持以下值：
            - "list": 查看所有注册人员列表
            - "delete": 删除指定人员（需同时提供 name 参数）
        name: 人员姓名（字符串，可选）。delete 操作时必填。

    Returns:
        JSON 字符串：
        - action="list" 时：type="person_list", count=人员数,
            persons=人员列表（每项包含 id, name, category, department 等）
        - action="delete" 时：type="person_deleted", name=已删除人员名,
            message=操作结果提示
    """
    if action == "list":
        # 列表查看：获取所有注册人员
        persons = await db_agent.get_all_persons()
        return json.dumps({
            "type": "person_list",
            "count": len(persons),
            "persons": persons,
        }, ensure_ascii=False, indent=2, default=str)

    elif action == "delete" and name:
        # 删除操作：同时从数据库和人脸特征库中移除
        await db_agent.delete_person(name)
        face_service.remove_face(name)
        return json.dumps({
            "type": "person_deleted",
            "name": name,
            "message": f"已成功删除人员：{name}",
        }, ensure_ascii=False)

    else:
        # 未匹配操作或参数不合法时，默认返回列表
        persons = await db_agent.get_all_persons()
        return json.dumps({
            "type": "person_list",
            "count": len(persons),
            "persons": persons,
        }, ensure_ascii=False, indent=2, default=str)


# ==================== 告警规则 ====================
# 用于查看当前配置的告警规则，只读操作

@tool
async def alert_rules() -> str:
    """
    查看告警规则配置：当前有哪些告警规则、是否已启用。

    适用场景（正例）:
    - 用户问"告警设置"、"有哪些告警规则"、"告警规则是什么"
    - 用户想了解当前告警配置

    不适用场景（反例）:
    - 添加或修改告警规则（需通过前端接口操作）
    - 查询实时画面（用 realtime_check）

    Returns:
        JSON 字符串，结构如下：
        - type: "alert_rules"
        - count: 规则数量（int）
        - rules: 规则列表，每项包含 id, name, condition_type,
            condition_value, enabled
    """
    # 从数据库获取所有告警规则
    rules = await db_agent.get_alert_rules()
    return json.dumps({
        "type": "alert_rules",
        "count": len(rules),
        "rules": rules,
    }, ensure_ascii=False, indent=2)


# ==================== 摄像头状态 ====================
# 用于查看摄像头配置和实时运行状态，综合运行时状态与数据库配置

@tool
async def camera_status() -> str:
    """
    查看摄像头配置和运行状态：有哪些摄像头、是否在线、在哪个位置。

    适用场景（正例）:
    - 用户问"有哪些摄像头"、"摄像头状态"、"摄像头列表"
    - 用户想了解摄像头在线情况

    不适用场景（反例）:
    - 查看摄像头的实时画面（用 realtime_check）
    - 添加或配置摄像头（需通过前端接口操作）

    工具组合建议：
    - 可先调用本工具查看摄像头列表，再用 realtime_check 查看具体画面

    Returns:
        JSON 字符串，结构如下：
        - type: "camera_status"
        - running_cameras: 当前运行中的摄像头状态 dict（来自 camera_manager）
        - configured_cameras: 数据库中配置的摄像头列表（每项包含
            id, name, source, location, status, fps）
    """
    # 获取运行时的摄像头状态（来自 camera_service）
    cameras = camera_manager.get_status()
    # 获取数据库中的摄像头配置记录
    db_cameras = await db_agent.get_cameras()

    return json.dumps({
        "type": "camera_status",
        "running_cameras": cameras,
        "configured_cameras": db_cameras,
    }, ensure_ascii=False, indent=2, default=str)
