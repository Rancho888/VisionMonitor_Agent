# Vision Monitor Agent — 快速上手

基于多 Agent 协作的智能视觉监控系统：实时人脸识别 + 自然语言对话查询 + 多路摄像头 + 告警规则。

完整的项目介绍、技术架构、API 接口说明见 [README.md](./README.md)。

---

## 环境要求

- **Docker 方式**：Docker 20+、Docker Compose
- **本地方式**：Python 3.10、Node.js >= 16
- **大模型 API Key**：需要一个兼容 OpenAI Chat Completions 接口的服务（通义千问 / DeepSeek / Ollama 都可）

---

## 一、Docker 启动（推荐）

> ⚠️ **第一次启动前必须先准备好 `backend/.env`**，否则容器能起来但所有 LLM 相关功能（对话、多模态分析）会失败。
>
> `docker-compose.yml` 第 17 行 `env_file: ./backend/.env` 只在文件存在时注入环境变量，**文件不存在不会报错**，要到调用 LLM 时才暴露出问题。

### 启动

```bash
# 1. 复制环境变量模板并填入真实 API Key
cp .env.example backend/.env
# 编辑 backend/.env，把 LLM_API_KEY 替换为你的真实 key

# 2. 一键启动（后端 + 前端 + nginx）
docker-compose up -d --build

# 3. 打开浏览器
#    前端页面：  http://localhost:3000
#    后端 API：  http://localhost:8000/docs
```

### 只想跑监控本身、不用 LLM？

可以。执行 `touch backend/.env` 留空文件即可。实时画面、人脸检测/识别都不依赖 LLM，只有"对话"接口会失败。

### 常用命令

```bash
docker-compose logs -f backend    # 查看后端日志
docker-compose logs -f frontend   # 查看前端日志
docker-compose down              # 停止服务
docker-compose down -v           # 停止并清除数据（谨慎！）
```

---

## 二、本地开发模式

```bash
# 1. 后端
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
cp .env.example backend/.env
# 编辑 backend/.env，填入 LLM_API_KEY
python -m backend.app.main

# 2. 前端（新开一个终端）
cd frontend
npm install
npm run dev
```

启动后访问：

- 前端：http://localhost:3000
- 后端 API 文档：http://localhost:8000/docs

---

## 三、首次使用流程

1. **添加摄像头**：进入"摄像头管理"，填入 RTSP URL 或本地摄像头索引，启动摄像头
2. **注册人员**：进入"人像库管理"，上传人员照片（支持同一人多张照片，提高识别精度）
3. **启动识别**：实时画面上会自动标注识别出的人脸，陌生人单独标红
4. **自然语言查询**：在对话窗口输入，例如"今天来过谁"、"陌生人有多少"、"某人最近来过几次"

---

## 四、配置大模型

`.env` 里支持三种后端（任何兼容 OpenAI Chat Completions 接口的模型都可以）：

| 提供方 | LLM_BASE_URL | LLM_MODEL_NAME |
|--------|-------------|----------------|
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen3.7-plus` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 本地 Ollama | `http://localhost:11434/v1` | `llava` |

---

## 五、常见问题

**Q: 启动后浏览器看不到画面？**
A: 检查摄像头是否正确添加并启动；本地摄像头注意浏览器/系统权限。

**Q: 人脸识别准确率低？**
A: 对同一人追加多张照片可以显著提高识别精度；检查光照、人脸角度是否清晰。

**Q: 想清空所有识别记录？**
A: 调用 API `DELETE /api/records/clear`，或直接删除 `backend/data/monitor.db`。

**Q: 后端启动报 "Invalid API key"？**
A: `backend/.env` 里的 `LLM_API_KEY` 没填/填错。注意 Docker 模式下 `.env` 必须放在 `backend/` 目录下。

**Q: 摄像头数量很多时性能跟不上？**
A: 在摄像头管理页面调低每路摄像头的帧率；服务层默认最低 0.6 秒间隔执行检测。

---

## 许可

本项目仅供作者本人私有使用，未经许可不得复制、分发、修改或商用。

All rights reserved.