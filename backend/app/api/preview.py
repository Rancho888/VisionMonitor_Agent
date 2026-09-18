"""
摄像头画面预览页面模块 —— 提供浏览器直接访问的实时预览页面

包含的端点：
1. GET /preview/{camera_id} —— 浏览器实时预览摄像头画面（返回 HTML 页面）

模块职责：
- 生成独立的 HTML 页面，内嵌 JavaScript WebSocket 客户端
- 通过 WebSocket 连接 /api/camera/stream/{camera_id} 获取实时视频流
- 展示画面帧、检测人数、识别人员信息（姓名、置信度、检测分）
- 支持已知人员（绿色标识）和未知人员（红色标识）的区分显示

使用方式：
- 直接浏览器访问 http://localhost:8000/preview/{camera_id}
- 例如 http://localhost:8000/preview/phone1
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

# 无路由前缀（预览页面直接在根路径下），标签为 preview
router = APIRouter(tags=["preview"])


@router.get("/preview/{camera_id}", response_class=HTMLResponse)
async def preview_camera(camera_id: str):
    """
    浏览器实时预览摄像头画面

    HTTP方法: GET
    路径: /preview/{camera_id}
    功能: 返回一个完整的 HTML 页面，通过 WebSocket 接收实时视频流并展示

    参数:
        camera_id: 摄像头唯一标识（如 "phone1"、"cam_001"）

    返回值: HTMLResponse —— 包含内嵌 CSS 和 JavaScript 的完整 HTML 页面

    页面元素说明：
    - h2 标题：显示摄像头ID
    - #frame (img)：实时画面展示区域，通过 base64 更新 src
    - #info (div)：状态信息（连接中/检测到人数/连接断开）
    - #persons (div)：识别人员列表，已知人员绿色、未知人员红色

    WebSocket 连接:
    - 连接地址: ws://{host}/api/camera/stream/{camera_id}
    - 接收消息格式: {{"type": "frame", "image_base64": "...", "total_persons": N, "persons": [...]}}
    - 每个 person 对象包含: name, confidence, detection_score, is_unknown
    """
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>摄像头预览 - {camera_id}</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                background: #1a1a2e;
                color: #e2e8f0;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 24px;
                -webkit-font-smoothing: antialiased;
            }}
            /* 标题区域：使用 SVG 相机图标 + 摄像头名称 */
            h2 {{
                margin-bottom: 16px;
                color: #60a5fa;
                font-size: 20px;
                font-weight: 600;
                display: flex;
                align-items: center;
                gap: 8px;
            }}
            h2 svg {{ opacity: 0.8; }}
            /* 画面展示区域：限制最大尺寸，圆角边框 */
            #frame {{
                max-width: 90vw;
                max-height: 75vh;
                border: 2px solid #334155;
                border-radius: 10px;
                box-shadow: 0 4px 24px rgba(0,0,0,0.4);
            }}
            /* 状态信息栏 */
            #info {{
                margin-top: 14px;
                font-size: 14px;
                color: #94a3b8;
                display: flex;
                align-items: center;
                gap: 6px;
            }}
            /* 状态圆点指示器 */
            .status-dot {{
                display: inline-block;
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: #f59e0b;
            }}
            .status-dot.connected {{ background: #22c55e; box-shadow: 0 0 6px rgba(34,197,94,0.5); }}
            .status-dot.error {{ background: #ef4444; }}
            .status-dot.disconnected {{ background: #64748b; }}
            /* 人员信息列表容器 */
            #persons {{
                margin-top: 14px;
                text-align: left;
                max-width: 90vw;
                width: 100%;
            }}
            /* 人员信息卡片样式 */
            .person {{
                background: #16213e;
                padding: 8px 14px;
                margin: 5px 0;
                border-radius: 8px;
                font-size: 14px;
                border: 1px solid #1e293b;
                transition: background 0.15s;
            }}
            .person:hover {{ background: #1c2a4a; }}
            /* 已知人员绿色标识 */
            .known {{ color: #4ade80; font-weight: 600; }}
            /* 未知人员红色标识 */
            .unknown {{ color: #f87171; font-weight: 600; }}
        </style>
    </head>
    <body>
        <h2>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
            {camera_id}
        </h2>
        <img id="frame" src="" alt="正在加载画面...">
        <div id="info"><span class="status-dot"></span> 正在连接摄像头...</div>
        <div id="persons"></div>

        <script>
            // 建立 WebSocket 连接到摄像头视频流端点
            const ws = new WebSocket("ws://" + location.host + "/api/camera/stream/{camera_id}");
            const infoEl = document.getElementById("info");

            ws.onopen = () => {{
                infoEl.innerHTML = '<span class="status-dot connected"></span> 已连接，等待画面...';
            }};

            ws.onmessage = (event) => {{
                const data = JSON.parse(event.data);
                // 处理视频帧消息：更新画面和识别结果
                if (data.type === "frame") {{
                    // 将 base64 编码的 JPEG 数据设置为图片 src
                    document.getElementById("frame").src = "data:image/jpeg;base64," + data.image_base64;
                    // 更新检测人数信息
                    infoEl.innerHTML = '<span class="status-dot connected"></span> 检测到 ' + data.total_persons + ' 人';
                    // 构建识别人员列表 HTML
                    let html = "";
                    (data.persons || []).forEach(p => {{
                        // 根据 is_unknown 标记选择不同的 CSS 类（绿色/红色）
                        const cls = p.is_unknown ? "unknown" : "known";
                        html += '<div class="person">';
                        html += '<span class="' + cls + '">' + (p.name || "未识别") + '</span> — 相似度: ' + p.confidence + '% | 检测分: ' + p.detection_score;
                        html += '</div>';
                    }});
                    document.getElementById("persons").innerHTML = html;
                }}
            }};
            // WebSocket 连接失败处理
            ws.onerror = () => {{
                infoEl.innerHTML = '<span class="status-dot error"></span> 连接失败，请确认摄像头已启动';
            }};
            // WebSocket 连接断开处理
            ws.onclose = () => {{
                infoEl.innerHTML = '<span class="status-dot disconnected"></span> 连接已断开';
            }};
        </script>
    </body>
    </html>
    """
"""
摄像头画面预览页面
直接浏览器访问 http://localhost:8000/preview/phone1
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["preview"])


@router.get("/preview/{camera_id}", response_class=HTMLResponse)
async def preview_camera(camera_id: str):
    """浏览器实时预览摄像头画面"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>摄像头预览 - {camera_id}</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                background: #1a1a2e;
                color: #e2e8f0;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 24px;
                -webkit-font-smoothing: antialiased;
            }}
            h2 {{
                margin-bottom: 16px;
                color: #60a5fa;
                font-size: 20px;
                font-weight: 600;
                display: flex;
                align-items: center;
                gap: 8px;
            }}
            h2 svg {{ opacity: 0.8; }}
            #frame {{
                max-width: 90vw;
                max-height: 75vh;
                border: 2px solid #334155;
                border-radius: 10px;
                box-shadow: 0 4px 24px rgba(0,0,0,0.4);
            }}
            #info {{
                margin-top: 14px;
                font-size: 14px;
                color: #94a3b8;
                display: flex;
                align-items: center;
                gap: 6px;
            }}
            .status-dot {{
                display: inline-block;
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: #f59e0b;
            }}
            .status-dot.connected {{ background: #22c55e; box-shadow: 0 0 6px rgba(34,197,94,0.5); }}
            .status-dot.error {{ background: #ef4444; }}
            .status-dot.disconnected {{ background: #64748b; }}
            #persons {{
                margin-top: 14px;
                text-align: left;
                max-width: 90vw;
                width: 100%;
            }}
            .person {{
                background: #16213e;
                padding: 8px 14px;
                margin: 5px 0;
                border-radius: 8px;
                font-size: 14px;
                border: 1px solid #1e293b;
                transition: background 0.15s;
            }}
            .person:hover {{ background: #1c2a4a; }}
            .known {{ color: #4ade80; font-weight: 600; }}
            .unknown {{ color: #f87171; font-weight: 600; }}
        </style>
    </head>
    <body>
        <h2>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
            {camera_id}
        </h2>
        <img id="frame" src="" alt="正在加载画面...">
        <div id="info"><span class="status-dot"></span> 正在连接摄像头...</div>
        <div id="persons"></div>

        <script>
            const ws = new WebSocket("ws://" + location.host + "/api/camera/stream/{camera_id}");
            const infoEl = document.getElementById("info");

            ws.onopen = () => {{
                infoEl.innerHTML = '<span class="status-dot connected"></span> 已连接，等待画面...';
            }};

            ws.onmessage = (event) => {{
                const data = JSON.parse(event.data);
                if (data.type === "frame") {{
                    document.getElementById("frame").src = "data:image/jpeg;base64," + data.image_base64;
                    infoEl.innerHTML = '<span class="status-dot connected"></span> 检测到 ' + data.total_persons + ' 人';
                    let html = "";
                    (data.persons || []).forEach(p => {{
                        const cls = p.is_unknown ? "unknown" : "known";
                        html += '<div class="person">';
                        html += '<span class="' + cls + '">' + (p.name || "未识别") + '</span> — 相似度: ' + p.confidence + '% | 检测分: ' + p.detection_score;
                        html += '</div>';
                    }});
                    document.getElementById("persons").innerHTML = html;
                }}
            }};
            ws.onerror = () => {{
                infoEl.innerHTML = '<span class="status-dot error"></span> 连接失败，请确认摄像头已启动';
            }};
            ws.onclose = () => {{
                infoEl.innerHTML = '<span class="status-dot disconnected"></span> 连接已断开';
            }};
        </script>
    </body>
    </html>
    """
