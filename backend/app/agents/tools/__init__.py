"""
Tools 层 - LangChain Tool 聚合导出
"""
from backend.app.agents.tools.monitor_tools import (
    realtime_check,
    history_query,
    statistics,
    person_manage,
    alert_rules,
    camera_status,
)

# 所有可用 Tool 列表（注入 Agent）
ALL_TOOLS = [
    realtime_check,
    history_query,
    statistics,
    person_manage,
    alert_rules,
    camera_status,
]
