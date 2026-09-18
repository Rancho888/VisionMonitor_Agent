"""
主控 Agent（Orchestrator）- 基于 LangChain bind_tools + 手动 ReAct 循环实现

模块职责：
    1. 接收用户消息，通过 LLM 自动决策调用哪个 Tool（替代手工 if/elif 路由）
    2. 两阶段流式输出：先 ainvoke 决策调用工具，再 astream_events 逐 token 输出最终回复
    3. 维护多会话对话上下文（按 session_id 隔离）

架构说明：
    - 所有 Tool 通过 bind_tools 注入 LLM，由 LLM 自主选择调用
    - ReAct 循环最多 5 轮，防止无限工具调用
    - 流式输出阶段出错时，fallback 到非流式结果保证可用性
"""
import json
from typing import Dict, List, AsyncGenerator

from langchain_core.messages import (
    HumanMessage, AIMessage, SystemMessage, ToolMessage
)

from backend.app.agents.model_factory import model_factory
from backend.app.agents.tools import ALL_TOOLS

# 对话上下文存储：key=session_id，value=该会话的历史消息列表
# 每个会话最多保留 20 条消息（10 轮对话），构建 LLM 上下文时取最近 6 条（3 轮）
conversation_store: Dict[str, List[Dict]] = {}

# Agent 系统提示词
# 结构化设计：角色定义 → 能力边界 → 工具使用指南 → 输出规范 → 约束规则 → 异常处理
SYSTEM_PROMPT = """
# 角色定义
你是一个专业的智能监控助手（Vision Monitor Agent），运行在本地监控系统上，
通过调用工具获取实时监控数据、历史记录和统计信息，为用户提供准确、有用的监控相关回答。

# 能力边界
你 **只能** 通过以下已注册工具获取数据，不具备任何超出工具范围的监控能力：
| 工具 | 功能 | 典型用户意图 |
|------|------|-------------|
| realtime_check | 实时检测当前画面中的人员 | "现在谁在"、"看看监控"、"实时画面" |
| history_query | 查询某人的历史出现记录 | "张三最近来过吗"、"今天谁来了" |
| statistics | 高频人员排名与统计 | "谁来得最多"、"排名"、"统计" |
| person_manage | 查看/管理注册人员 | "人员列表"、"删除XXX" |
| alert_rules | 查看告警规则配置 | "告警设置"、"告警规则" |
| camera_status | 查看摄像头配置和状态 | "有哪些摄像头"、"摄像头状态" |

# 工具使用指南（决策流程）
收到用户消息后，按以下步骤思考：
1. **意图分析**：判断用户想了解什么（实时画面 / 历史查询 / 统计 / 人员管理 / 告警 / 摄像头 / 闲聊）
2. **工具选择**：
   - 实时画面相关 → `realtime_check`
   - 某人的历史记录 → `history_query`（传入 person_name）
   - 全部历史记录 → `history_query`（不传 person_name）
   - 排名/统计/高频 → `statistics`
   - 人员列表/删除 → `person_manage`（action="list" 或 "delete"）
   - 告警相关 → `alert_rules`
   - 摄像头配置/状态 → `camera_status`
   - 纯闲聊/问候 → 不调用工具，直接回复
3. **结果解读**：根据工具返回的 JSON 数据组织回复

# 输出格式规范
- 使用中文回复，语气友好自然
- 适当使用 emoji 增加可读性（如 👤 表示人员、📊 表示统计、📷 表示摄像头）
- 多人信息使用列表或表格呈现
- 时间信息使用相对时间（如"3小时前"而非绝对时间戳）
- 数值保留原始精度，不要四舍五入

# 约束规则（必须严格遵守）
- **禁止编造数据**：所有监控数据必须来自工具返回结果，绝不可凭空捏造人名、时间、次数
- **禁止推测**：如果工具未返回某信息，明确告知用户"暂无该数据"，不要猜测
- **工具优先**：涉及监控数据的问答必须先调用工具，不要依赖对话历史中的旧数据回答新问题

# 异常处理
- 工具返回 `camera_count=0` 或 `status=no_camera` → 告知用户需先在前端添加并启动摄像头
- 工具返回 `error` 字段 → 向用户说明"获取数据时遇到问题"并简述错误，建议重试
- 工具返回空列表（records=[] 或 persons=[]）→ 如实告知"暂无相关记录"
- 工具调用失败 → 告知用户系统暂时不可用，建议稍后重试
- 多个工具组合调用 → 按顺序汇报各工具结果，确保不遗漏
"""

# Tool name -> callable 映射表，用于在 ReAct 循环中根据名称查找并执行对应工具
_TOOL_MAP = {t.name: t for t in ALL_TOOLS}


def _build_messages(history: List[Dict], user_message: str) -> List:
    """
    构建 LangChain Message 列表，用于传入 LLM。

    将系统提示词 + 历史对话（最近 3 轮 = 6 条消息）+ 当前用户消息
    组装为 LLM 可理解的消息序列。

    Args:
        history: 对话历史列表，每条包含 role 和 content
        user_message: 当前用户输入的消息

    Returns:
        LangChain Message 对象列表
    """
    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    # 取最近 6 条历史（即 3 轮对话），平衡上下文长度与 token 开销
    for h in history[-6:]:
        if h["role"] == "user":
            messages.append(HumanMessage(content=h["content"]))
        elif h["role"] == "assistant":
            messages.append(AIMessage(content=h["content"]))
    messages.append(HumanMessage(content=user_message))
    return messages


async def _execute_tools(tool_calls: list, messages: List) -> List:
    """
    执行 LLM 决策的工具调用，返回 ToolMessage 列表供 ReAct 循环使用。

    每个 tool_call 包含 name（工具名）、args（参数）、id（调用标识）。
    工具执行失败时返回包含 error 字段的 JSON，而非抛出异常，
    确保 ReAct 循环能继续运行。

    Args:
        tool_calls: LLM 返回的工具调用列表
        messages: 当前消息上下文（保留参数，供未来扩展使用）

    Returns:
        ToolMessage 列表，每条与对应的 tool_call 通过 tool_call_id 关联
    """
    tool_messages = []
    for tc in tool_calls:
        tool_name = tc.get("name", "")
        tool_args = tc.get("args", {})
        tool_id = tc.get("id", "")

        tool_fn = _TOOL_MAP.get(tool_name)
        if tool_fn:
            try:
                # 异步执行工具函数
                result = await tool_fn.ainvoke(tool_args)
            except Exception as e:
                # 工具执行异常时返回错误信息，而非中断整个循环
                result = json.dumps({"error": str(e), "tool": tool_name}, ensure_ascii=False)
        else:
            # 未知工具名：LLM 幻觉出了不存在的工具
            result = json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)

        tool_messages.append(ToolMessage(content=str(result), tool_call_id=tool_id))

    return tool_messages


class OrchestratorAgent:
    """
    基于 LangChain bind_tools 的主控 Agent。

    核心机制：
        - 通过 bind_tools 将所有监控工具注入 LLM，由 LLM 自主选择调用
        - 采用两阶段处理：Phase 1 非流式决策 + Phase 2 流式输出
        - ReAct 循环最多 5 轮，支持多工具组合调用
    """

    def _get_llm(self, streaming: bool = False):
        """
        获取绑定了所有监控工具的 LLM 实例。

        Args:
            streaming: 是否启用流式输出（Phase 2 为 True，Phase 1 为 False）

        Returns:
            绑定了 ALL_TOOLS 的 ChatOpenAI 实例
        """
        return model_factory.get_chat_model(
            temperature=0.3,  # 低温度确保工具选择稳定
            streaming=streaming,
            bind_tools=ALL_TOOLS,
        )

    async def process_message(
        self,
        message: str,
        session_id: str = "default",
    ) -> AsyncGenerator[str, None]:
        """
        处理用户消息，流式返回回复文本。

        两阶段处理流程：
            Phase 1（非流式）：通过 ainvoke 让 LLM 决策调用工具，
                支持最多 5 轮 ReAct 循环（工具调用 → 获取结果 → 继续推理）
            Phase 2（流式）：将 Phase 1 积累的工具结果作为上下文，
                用 astream_events 逐 token 流式输出最终回复给用户

        Args:
            message: 用户发送的消息文本
            session_id: 会话标识，用于隔离不同用户/对话的上下文

        Yields:
            逐 token 的回复文本片段
        """
        # 获取或创建该会话的历史记录
        if session_id not in conversation_store:
            conversation_store[session_id] = []
        history = conversation_store[session_id]

        # 构建包含系统提示词 + 历史 + 当前消息的完整消息列表
        messages = _build_messages(history, message)

        # ====== Phase 1: 工具调用循环（非流式） ======
        # 用非流式模式让 LLM 决策调用哪些工具，支持多轮 ReAct
        llm_decision = self._get_llm(streaming=False)

        # 最大迭代次数：防止 LLM 陷入无限工具调用循环
        MAX_ITERATIONS = 5
        for _ in range(MAX_ITERATIONS):
            response = await llm_decision.ainvoke(messages)

            if response.tool_calls:
                # LLM 请求调用工具 → 执行工具并将结果追加到上下文
                messages.append(response)
                tool_msgs = await _execute_tools(response.tool_calls, messages)
                messages.extend(tool_msgs)
            else:
                # LLM 认为无需再调用工具 → 生成最终回复，结束循环
                messages.append(response)
                break

        # ====== Phase 2: 流式输出最终回复 ======
        # 移除 Phase 1 中 LLM 生成的最终 AIMessage，用流式模式重新生成
        last_msg = messages.pop()
        full_response = ""
        error_occurred = False

        llm_stream = self._get_llm(streaming=True)

        try:
            # 使用 astream_events v2 协议监听流式 token 事件
            async for event in llm_stream.astream_events(messages, version="v2"):
                if event["event"] == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if chunk.content and isinstance(chunk.content, str):
                        full_response += chunk.content
                        yield chunk.content

        except Exception as e:
            # 流式输出失败时的 fallback 策略：
            # 使用 Phase 1 中已生成的非流式结果，保证功能可用性
            full_response = last_msg.content if hasattr(last_msg, "content") and last_msg.content else ""
            if full_response:
                yield full_response
            else:
                error_msg = f"处理消息时出错: {str(e)}"
                yield error_msg
                full_response = error_msg
            error_occurred = True

        # ====== 保存对话历史 ======
        # 仅当有有效回复时才保存，避免空消息污染历史
        if full_response.strip():
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": full_response})
            # 历史超过 20 条时截断，保留最近 20 条（10 轮对话）
            if len(history) > 20:
                conversation_store[session_id] = history[-20:]


# 全局单例：供 API 层直接调用
orchestrator = OrchestratorAgent()
