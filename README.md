# Vision Monitor Agent

基于多 Agent 协作的智能视觉监控系统，融合实时人脸识别与自然语言交互，支持多路摄像头监控、人像库管理、历史记录查询与告警规则配置。

## 功能特性

- **实时监控**：多路摄像头画面采集 + 实时人脸检测与识别（InsightFace SCRFD + ArcFace）
- **智能对话**：自然语言交互查询监控数据，LLM 自主决策调用工具（ReAct 循环，6 大监控工具）
- **人像库管理**：注册、删除人员，支持多张照片追加以提升识别精度
- **历史记录**：识别记录分页查询、多条件筛选、统计分析与高频人员排名
- **告警规则**：黑名单出现、陌生人检测等规则配置
- **多路摄像头**：支持本地摄像头、RTSP 流、HTTP 流，画面旋转校正

## 技术架构

```
┌───────────────────────────────────────────────────────────────┐
│                      前端  (Vue 3 + Vite)                      │
│              TailwindCSS / Pinia / Axios / WebSocket          │
└──────────────┬────────────────────────────────┬───────────────┘
               │ HTTP / WebSocket / SSE          │
┌──────────────▼────────────────────────────────▼───────────────┐
│                     FastAPI 后端服务                           │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐   │
│  │  chat   │ │ camera  │ │ person  │ │ records │ │preview │   │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └───┬────┘   │
└───────┼───────────┼───────────┼───────────┼──────────┼────────┘
        │           │           │           │          │
┌───────▼───────────▼───────────▼───────────▼──────────▼───────┐
│                      Agent 编排层                             │
│  ┌──────────────────────────────────────────────────────┐    │
│  │            Orchestrator (主控 Agent)                  │    │
│  │    LangChain bind_tools + 手动 ReAct 循环             │     │
│  └──┬──────┬──────┬──────┬──────┬──────┬──────┬─────────┘    │
│     │      │      │      │      │      │      │              │
│  ┌──▼──┐┌──▼──┐┌──▼──┐┌──▼──┐┌──▼──┐┌──▼──┐                  │
│  │real ││hist ││stat ││pers ││alert││cam  │  6 大工具         │
│  │time ││query││istcs││mgmt ││rule ││stat │                  │
│  └──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘                  │
└─────┼───────┼───────┼───────┼───────┼───────┼────────────────┘
      │       │       │       │       │       │
┌─────▼───────▼───────▼───────▼───────▼───────▼────────────────┐
│                      服务层                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐    │
│  │ Vision Agent │  │Database Agent│  │    LLM Service   │    │
│  │ InsightFace  │  │  SQLAlchemy  │  │  通义千问/兼容     │    │
│  │ SCRFD+ArcFace│  │  aiosqlite   │  │  OpenAI 接口      │    │
│  │ FAISS 检索    │  │  SQLite     │   │                  │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

## 快速开始

### 环境要求

- Python 3.10
- Node.js >= 16
- 操作系统：Windows / Linux / macOS

### 安装步骤

**1. 克隆项目**

```bash
git clone <repository-url>
cd workspace_MonitorAgent
```

**2. 后端配置**

```bash
# 创建并激活虚拟环境
conda create -n monitor_agent python=3.10 -y
conda activate monitor_agent

# 安装 Python 依赖（推荐使用清华镜像源加速）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**3. 环境变量配置**

复制 `.env.example` 为 `backend/.env`，填入你的大模型 API 配置：

```bash
cp .env.example backend/.env
```

编辑 `backend/.env`：

```ini
# 大模型配置（必填）
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen3.7-plus

# 服务配置
HOST=0.0.0.0
PORT=8000

# 数据库路径
DATABASE_URL=sqlite+aiosqlite:///./data/monitor.db

# 人像库路径
FACE_DB_PATH=./data/face_db
```

支持的大模型后端：

| 提供方 | LLM_BASE_URL | LLM_MODEL_NAME |
|--------|-------------|----------------|
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen3.7-plus` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 本地 Ollama | `http://localhost:11434/v1` | `llava` |

> 只要兼容 OpenAI Chat Completions 接口的模型均可使用。

**4. 前端安装**

```bash
cd frontend
npm install
```

### 启动服务

**后端**

```bash
# 激活虚拟环境后，在项目根目录执行
python -m backend.app.main
```

默认监听 `0.0.0.0:8000`，启动后访问 http://localhost:8000/docs 查看 API 文档。

**前端开发模式**

```bash
cd frontend
npm run dev
```

开发服务器监听 `localhost:3000`，自动代理 `/api` 和 `/ws` 到后端。

**前端生产构建**

```bash
cd frontend
npm run build
```

构建产物输出到 `frontend/dist/`。

## 项目结构

```
worksapce_MonitorAgent/
├── backend/
│   ├── app/
│   │   ├── agents/                  # Agent 编排层
│   │   │   ├── orchestrator.py      # 主控 Agent（ReAct 循环 + 流式输出）
│   │   │   ├── vision_agent.py      # 视觉 Agent（人脸检测/识别/LLM 分析）
│   │   │   ├── database_agent.py    # 数据库 Agent（CRUD + 统计）
│   │   │   ├── model_factory.py     # LLM 模型工厂
│   │   │   └── tools/               # LangChain 工具定义
│   │   │       ├── __init__.py      # 工具聚合导出
│   │   │       └── monitor_tools.py # 6 大监控工具实现
│   │   ├── api/                     # API 路由层
│   │   │   ├── chat.py              # 对话接口（WebSocket / SSE / HTTP）
│   │   │   ├── camera.py            # 摄像头管理 + 视频流 + 人脸注册
│   │   │   ├── person.py            # 人像库管理（注册/删除/追加照片）
│   │   │   ├── records.py           # 识别记录查询/统计/截图
│   │   │   └── preview.py           # 浏览器实时预览页面
│   │   ├── services/                # 服务层
│   │   │   ├── camera_service.py    # 摄像头生命周期管理 + 帧采集
│   │   │   ├── face_service.py      # InsightFace 封装 + FAISS 特征管理
│   │   │   └── llm_service.py       # LLM 调用封装（多模态分析/比对）
│   │   ├── models/                  # 数据模型
│   │   │   ├── database.py          # SQLAlchemy ORM 模型 + 会话管理
│   │   │   └── schemas.py           # Pydantic 请求/响应模型
│   │   ├── data/uploads/            # 上传文件存储
│   │   └── main.py                  # 应用入口（FastAPI + 生命周期）
│   ├── data/
│   │   ├── face_db/                 # 人脸特征库（pkl + 图片文件）
│   │   ├── snapshots/               # 识别记录截图
│   │   ├── uploads/                 # 注册照片上传目录
│   │   └── monitor.db               # SQLite 数据库文件
│   └── .env                         # 环境变量配置
├── frontend/
│   ├── src/                         # Vue 3 前端源码
│   ├── index.html
│   ├── vite.config.js               # Vite 配置（含 API 代理）
│   └── package.json
├── requirements.txt                 # Python 依赖清单
├── .env.example                     # 环境变量模板
└── README.md
```

## API 接口概览

### 对话接口 (`/api/chat`)

| 方法 | 路径 | 说明 |
|------|------|------|
| WebSocket | `/api/chat/ws/{session_id}` | 实时对话（流式输出，推荐） |
| POST | `/api/chat/send` | 非流式对话（适合测试） |
| POST | `/api/chat/stream` | SSE 流式对话 |

### 摄像头管理 (`/api/camera`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/camera/list` | 获取所有摄像头状态 |
| POST | `/api/camera/add` | 添加摄像头 |
| POST | `/api/camera/start/{camera_id}` | 启动摄像头 |
| POST | `/api/camera/stop/{camera_id}` | 停止摄像头 |
| DELETE | `/api/camera/{camera_id}` | 删除摄像头 |
| PUT | `/api/camera/{camera_id}` | 编辑摄像头配置 |
| GET | `/api/camera/snapshot/{camera_id}` | 获取当前画面截图 |
| WebSocket | `/api/camera/stream/{camera_id}` | 实时视频流 |
| POST | `/api/camera/register-face` | 注册人脸 |
| POST | `/api/camera/update-fps` | 批量更新帧率 |
| POST | `/api/camera/update-rotation` | 更新画面旋转角度 |
| GET | `/api/camera/database` | 摄像头库完整数据 |

### 人像库管理 (`/api/persons`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/persons` | 获取所有人像库数据 |
| POST | `/api/persons/register` | 注册新人员（支持多张照片） |
| POST | `/api/persons/{name}/add-photo` | 追加照片 |
| GET | `/api/persons/{name}/avatar` | 获取人员头像 |
| GET | `/api/persons/{name}` | 获取人像详情 |
| DELETE | `/api/persons/{name}` | 删除人员 |

### 识别记录 (`/api/records`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/records` | 分页查询记录（多条件筛选） |
| GET | `/api/records/summary` | 今日/总览统计 |
| DELETE | `/api/records/clear` | 清空全部记录 |
| GET | `/api/records/snapshot/{id}` | 获取记录截图 |

### 其他

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 服务信息 |
| GET | `/health` | 健康检查 |
| GET | `/preview/{camera_id}` | 浏览器实时预览页面 |

## 核心设计

### Agent 编排

系统采用 **Orchestrator + Tools** 架构，基于 LangChain `bind_tools` 实现 LLM 自主决策：

1. **主控 Agent（Orchestrator）**：接收用户消息，通过 LLM 自动判断意图并选择调用工具
2. **ReAct 循环**：最多 5 轮迭代，支持多工具组合调用（如先查实时画面再查历史记录）
3. **两阶段流式输出**：
   - Phase 1（非流式）：LLM 决策 + 工具调用
   - Phase 2（流式）：逐 token 输出最终回复

6 大监控工具：

| 工具 | 功能 | 典型触发 |
|------|------|---------|
| `realtime_check` | 实时检测画面中人员 | "现在谁在XX"、"看看XX监控" |
| `history_query` | 查询历史识别记录 | "XX最近来过吗" |
| `statistics` | 高频人员排名与统计 | "谁来得最多" |
| `person_manage` | 管理注册人员 | "人员列表"、"删除XXX" |
| `alert_rules` | 查看告警规则 | "告警设置" |
| `camera_status` | 查看摄像头状态 | "有哪些摄像头" |

### 人脸识别流程

```
摄像头帧 → 缩放至 640 宽度
         → InsightFace SCRFD 人脸检测
         → ArcFace 提取 512 维特征向量
         → FAISS 与注册库比对（余弦相似度）
         → 阈值判定：已知人员 / 陌生人
         → 绘制标注框 + 去重写入数据库
         → 结果缓存供 WebSocket 推送
```

关键设计点：

- **线程池执行**：人脸检测在线程池中运行，避免阻塞 asyncio 事件循环
- **5 秒去重机制**：同一人名在 5 秒内只保存一次数据库记录
- **节流控制**：每路摄像头最低 0.6 秒间隔执行一次检测，防止 CPU 过载
- **二进制 WebSocket 推送**：视频流使用 `[元数据长度][元数据JSON][JPEG字节]` 格式，消除 base64 体积膨胀
- **多图注册**：支持对同一人追加多张照片，增加特征样本以提升识别准确率

## 开发说明

### 数据库

使用 SQLite 异步驱动（aiosqlite），ORM 层为 SQLAlchemy 2.0。应用启动时自动执行 `init_db()` 创建表结构。数据库文件默认位于 `data/monitor.db`。

四张核心表：

- **face_records**：人脸识别记录
- **person_info**：注册人员信息
- **alert_rules**：告警规则配置
- **camera_info**：摄像头配置

### 代码风格

- 后端模块均使用全局单例模式（`orchestrator`、`vision_agent`、`db_agent`、`face_service`、`camera_manager`）
- API 层仅做参数校验和路由转发，业务逻辑下沉到 Agent / Service 层
- 工具函数的 docstring 是 LLM 判断何时调用的核心依据，修改时需保持描述准确

### 前端代理配置

开发模式下 Vite 自动代理后端接口：

```javascript
// vite.config.js
proxy: {
  '/api': { target: 'http://localhost:8000', changeOrigin: true },
  '/ws':  { target: 'ws://localhost:8000', ws: true }
}
```
