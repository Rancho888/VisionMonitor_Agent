"""
对话 API 模块 —— 提供 AI 智能助手的对话交互接口

包含的端点：
1. WebSocket /api/chat/ws/{session_id}  —— 实时对话（流式输出 + 监控画面推送）
2. POST /api/chat/send                   —— 非流式对话（HTTP，适合测试/简单场景）
3. POST /api/chat/stream                 —— SSE 流式对话（HTTP，Server-Sent Events）

模块职责：
- 接收用户消息，调用 Orchestrator 进行意图识别和任务分发
- 支持流式和非流式两种输出模式
- WebSocket 接口支持心跳保活（ping/pong）和会话管理
"""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse
from backend.app.models.schemas import ChatRequest, ChatResponse, IntentType
from backend.app.agents.orchestrator import orchestrator

# 路由前缀 /api/chat，标签为 chat（用于 Swagger 文档分组）
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.websocket("/ws/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket 实时对话接口（支持流式输出 + 监控画面推送）

    HTTP方法: WebSocket
    路径: /api/chat/ws/{session_id}
    功能: 建立长连接，支持双向实时通信，用户发送文本消息后 AI 以流式方式逐字返回

    参数:
        session_id: 会话标识，用于区分不同用户的对话上下文

    消息协议（客户端 → 服务端）:
        - {"type": "chat", "message": "用户消息"} —— 发送对话消息
        - {"type": "ping"} —— 心跳探测

    消息协议（服务端 → 客户端）:
        - {"type": "connected", ...} —— 连接成功确认
        - {"type": "status", "message": "正在分析..."} —— 处理状态通知
        - {"type": "chat_chunk", "content": "片段文本"} —— 流式回复片段
        - {"type": "chat_done", "full_message": "完整文本"} —— 回复完成信号
        - {"type": "pong"} —— 心跳响应
        - {"type": "error", "message": "错误信息"} —— 异常通知

    返回值: 无（通过 WebSocket 持续推送消息）
    """
    # 第一步：接受 WebSocket 连接并发送连接确认消息
    await websocket.accept()
    await websocket.send_json({
        "type": "connected",
        "session_id": session_id,
        "message": "✅ 已连接到智能监控助手",
    })

    try:
        # 第二步：进入消息接收循环
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            # 处理对话消息类型
            if msg.get("type") == "chat":
                user_message = msg.get("message", "")

                # 发送"正在处理"状态通知，让前端展示加载动画
                await websocket.send_json({
                    "type": "status",
                    "message": "正在分析...",
                })

                # 调用 Orchestrator 处理消息，流式逐块返回 LLM 回复
                full_text = ""
                async for chunk in orchestrator.process_message(
                    message=user_message,
                    session_id=session_id,
                ):
                    # 每收到一个文本片段就立即推送给前端，实现打字机效果
                    full_text += chunk
                    await websocket.send_json({
                        "type": "chat_chunk",
                        "content": chunk,
                    })

                # 所有片段推送完毕后，发送完成信号（含完整文本，方便前端做最终渲染）
                await websocket.send_json({
                    "type": "chat_done",
                    "full_message": full_text,
                })

            # 处理心跳探测，保持连接活跃
            elif msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        # 客户端主动断开连接（正常行为，如关闭页面、切换路由等）
        print(f"🔌 WebSocket 断开: {session_id}")
    except Exception as e:
        # 服务端异常，将错误信息推送给客户端以便排查
        print(f"❌ WebSocket 错误: {e}")
        await websocket.send_json({"type": "error", "message": str(e)})


@router.post("/send")
async def chat_send(req: ChatRequest):
    """
    HTTP 非流式对话接口（适合测试和简单场景）

    HTTP方法: POST
    路径: /api/chat/send
    功能: 接收用户消息，等待 AI 完整处理后一次性返回响应

    参数:
        req: ChatRequest 请求体，包含 message（消息内容）、session_id（会话ID）等

    返回值: ChatResponse 响应体，包含完整的 AI 回复文本、意图类型、时间戳等

    注意: 该接口会等待所有回复片段生成完毕后才返回，响应时间较长
    """
    # 收集所有流式片段，拼接为完整回复
    full_response = ""
    async for chunk in orchestrator.process_message(
        message=req.message,
        session_id=req.session_id,
    ):
        full_response += chunk

    return ChatResponse(
        session_id=req.session_id,
        message=full_response,
        intent=IntentType.GENERAL_CHAT,
    )


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    """
    HTTP SSE 流式对话接口（Server-Sent Events）

    HTTP方法: POST
    路径: /api/chat/stream
    功能: 接收用户消息，以 SSE（Server-Sent Events）方式流式返回 AI 回复

    参数:
        req: ChatRequest 请求体，包含 message（消息内容）、session_id（会话ID）等

    返回值: StreamingResponse（text/event-stream），每个片段格式为:
        data: {"content": "文本片段"}\n\n
    流结束时发送:
        data: [DONE]\n\n

    特点:
    - 相比 WebSocket 更轻量，仅支持服务端向客户端单向推送
    - 设置 Cache-Control: no-cache 和 X-Accel-Buffering: no 禁用代理缓冲
    """
    async def event_stream():
        """
        SSE 事件流生成器

        遍历 Orchestrator 的流式输出，逐个片段以 SSE 格式 yield。
        所有片段发送完毕后，发送 [DONE] 标记告知客户端流已结束。
        """
        async for chunk in orchestrator.process_message(
            message=req.message,
            session_id=req.session_id,
        ):
            yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
        # 发送流结束标记，前端据此停止等待
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",       # 禁用缓存，确保实时性
            "X-Accel-Buffering": "no",          # 禁用 Nginx 等反向代理的缓冲
        },
    )
"""
对话 API - WebSocket + HTTP
"""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse
from backend.app.models.schemas import ChatRequest, ChatResponse, IntentType
from backend.app.agents.orchestrator import orchestrator

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.websocket("/ws/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket 对话接口（支持流式输出 + 监控画面推送）
    """
    await websocket.accept()
    await websocket.send_json({
        "type": "connected",
        "session_id": session_id,
        "message": "✅ 已连接到智能监控助手",
    })

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "chat":
                user_message = msg.get("message", "")

                # 先发送"正在处理"
                await websocket.send_json({
                    "type": "status",
                    "message": "正在分析...",
                })

                # 流式返回 LLM 回复
                full_text = ""
                async for chunk in orchestrator.process_message(
                    message=user_message,
                    session_id=session_id,
                ):
                    full_text += chunk
                    await websocket.send_json({
                        "type": "chat_chunk",
                        "content": chunk,
                    })

                # 发送完成信号
                await websocket.send_json({
                    "type": "chat_done",
                    "full_message": full_text,
                })

            elif msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        print(f"🔌 WebSocket 断开: {session_id}")
    except Exception as e:
        print(f"❌ WebSocket 错误: {e}")
        await websocket.send_json({"type": "error", "message": str(e)})


@router.post("/send")
async def chat_send(req: ChatRequest):
    """
    HTTP 对话接口（非流式，适合测试）
    """
    full_response = ""
    async for chunk in orchestrator.process_message(
        message=req.message,
        session_id=req.session_id,
    ):
        full_response += chunk

    return ChatResponse(
        session_id=req.session_id,
        message=full_response,
        intent=IntentType.GENERAL_CHAT,
    )


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    """
    HTTP 流式对话接口（SSE）
    """
    async def event_stream():
        async for chunk in orchestrator.process_message(
            message=req.message,
            session_id=req.session_id,
        ):
            yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
