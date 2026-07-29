# Computer Use Demo — FastAPI Backend

基于 [Anthropic Computer Use Demo](https://github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo) 技术栈，将实验性的 Streamlit 界面替换为**可扩展的 FastAPI 后端**，提供会话管理、实时流式传输、VNC 集成和数据库持久化。

> [!CAUTION]
> Computer use 是 Beta 功能。使用 computer use 与互联网交互时存在独特风险。请采取预防措施：
> 1. 使用具有最小权限的专用虚拟机或容器
> 2. 避免让模型访问敏感数据（如账户登录信息）
> 3. 将互联网访问限制在允许列表中的域名
> 4. 要求人工确认可能产生实际后果的决策
>
> 更多安全信息见 [Anthropic Computer Use 文档](https://docs.anthropic.com/en/docs/agents-and-tools/computer-use)。

---

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                     Docker Container                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐   │
│  │  Xvfb    │  │  mutter  │  │  x11vnc :5900        │   │
│  │  :1      │  │  (WM)    │  │                      │   │
│  └──────────┘  └──────────┘  └──────────┬───────────┘   │
│                                         │               │
│  ┌──────────────────────────────────────┼───────────┐   │
│  │              noVNC :6080             │           │   │
│  │         (websockify 代理)            │           │   │
│  └──────────────────┬───────────────────┘           │   │
│                     │                               │   │
│  ┌──────────────────┴───────────────────────────┐   │
│  │          FastAPI Backend :8000                │   │
│  │  ┌─────────────┐  ┌──────────┐  ┌─────────┐  │   │
│  │  │ REST API    │  │WebSocket │  │ WS VNC  │  │   │
│  │  │ /api/*      │  │ /ws/*    │  │ Proxy   │  │   │
│  │  └──────┬──────┘  └────┬─────┘  └────┬────┘  │   │
│  │         │              │             │        │   │
│  │  ┌──────┴──────────────┴─────────────┴────┐   │   │
│  │  │       Session Manager + DB             │   │   │
│  │  │  (SQLAlchemy + aiosqlite + Lock)       │   │   │
│  │  └──────────────────┬─────────────────────┘   │   │
│  └─────────────────────┼─────────────────────────┘   │
│                        │                             │
│  ┌─────────────────────┴─────────────────────────┐   │
│  │  Agent Loop (sampling.py)                     │   │
│  │  ┌──────────┬──────────┬──────────┬────────┐  │   │
│  │  │Anthropic │ Bedrock  │  Vertex  │DeepSeek│  │   │
│  │  └──────────┴──────────┴──────────┴────────┘  │   │
│  └───────────────────────────────────────────────┘   │
│                                                      │
│  ┌───────────────────────────────────────────────┐   │
│  │       Static Frontend (Vanilla HTML/JS)       │   │
│  └───────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## 核心功能

| 功能 | 实现 | 技术栈 |
|------|------|--------|
| 会话管理 API | CRUD REST API | FastAPI + Pydantic |
| 实时流式传输 | WebSocket 事件推送 | FastAPI WebSocket |
| VNC 桌面连接 | x11vnc + noVNC + WS 代理 | Docker + asyncio |
| 聊天历史持久化 | SQLite 数据库 | SQLAlchemy + aiosqlite |
| 并发会话支持 | 每会话锁 + 全局锁 | asyncio.Lock |
| 多 Provider 支持 | Anthropic / Bedrock / Vertex / DeepSeek | SDK 适配层 |
| Docker 一键部署 | docker compose up | Docker + Compose |
| 简单前端 | Vanilla HTML/JS SPA | 无框架 |

---

## 快速开始

### 前置条件

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)（Windows/Mac）或 Docker Engine（Linux）
- Anthropic API Key（从 [Claude Console](https://console.anthropic.com/) 获取）

### 1. 配置环境变量

```bash
# 复制示例配置
# 在 computer-use-demo 目录下创建 .env 文件
```

**.env 示例：**
```env
# 必填 — 选择 provider
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
API_PROVIDER=anthropic

# 可选 — DeepSeek 支持
# API_PROVIDER=deepseek
# DEEPSEEK_API_KEY=sk-your-deepseek-key
# DEEPSEEK_BASE_URL=https://api.deepseek.com
# DEEPSEEK_MODEL=deepseek-chat
```

### 2. 构建并启动

```bash
cd computer-use-demo
docker compose up --build -d
```

### 3. 访问服务

| 服务 | URL |
|------|-----|
| **前端界面** | [http://localhost:8000](http://localhost:8000) |
| **API 文档 (Swagger)** | [http://localhost:8000/docs](http://localhost:8000/docs) |
| **VNC 桌面** | [http://localhost:6080/vnc.html](http://localhost:6080/vnc.html) |

### 4. 使用前端

1. 打开 [http://localhost:8000](http://localhost:8000)
2. 点击 **＋** 创建新会话
3. 配置 Provider、Model、API Key
4. 在聊天框输入任务描述，如 "打开 Firefox 搜索天气"
5. 勾选 **Show VNC** 查看虚拟桌面操作

---

## API 文档

### REST API

| 方法 | 端点 | 说明 | 状态码 |
|------|------|------|--------|
| `POST` | `/api/sessions` | 创建会话 | 201 |
| `GET` | `/api/sessions` | 列出所有会话 | 200 |
| `GET` | `/api/sessions/{id}` | 获取会话详情 | 200 |
| `DELETE` | `/api/sessions/{id}` | 删除会话 | 204 |
| `POST` | `/api/sessions/{id}/chat` | 发送消息（启动 agent） | 200 |
| `POST` | `/api/sessions/{id}/cancel` | 取消正在运行的 agent | 200 |
| `GET` | `/api/sessions/{id}/messages` | 获取会话消息历史 | 200 |
| `GET` | `/api/health` | 健康检查 | 200 |

#### 创建会话

```bash
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Session",
    "config": {
      "model": "claude-sonnet-4-20250514",
      "provider": "anthropic",
      "api_key": "sk-ant-..."
    }
  }'
```

**响应：**
```json
{
  "id": "uuid-xxxx",
  "name": "My Session",
  "status": "active",
  "config": { ... },
  "created_at": "2026-07-27T12:00:00+00:00",
  "updated_at": "2026-07-27T12:00:00+00:00"
}
```

#### 发送消息

```bash
curl -X POST http://localhost:8000/api/sessions/{id}/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Open Firefox and search for weather"}'
```

#### 获取消息历史

```bash
curl http://localhost:8000/api/sessions/{id}/messages
```

### WebSocket API

#### 会话事件流

```
ws://localhost:8000/ws/sessions/{session_id}
```

**事件类型：**

| 事件 | 说明 |
|------|------|
| `connected` | 连接建立，包含 session_id 和 is_running 状态 |
| `status` | Agent 状态变化（starting, api_call, processing） |
| `text_delta` | 流式文本增量 |
| `thinking` | 模型思考过程 |
| `tool_use` | 工具调用（computer, bash, edit） |
| `tool_result` | 工具执行结果 |
| `done` | Agent 任务完成 |
| `cancelled` | 任务被取消 |
| `error` | 错误信息 |
| `ping` | 心跳保活（30秒间隔） |

#### 客户端示例 (JavaScript)

```javascript
const ws = new WebSocket(`ws://localhost:8000/ws/sessions/${sessionId}`);

ws.onmessage = (event) => {
  const { type, data } = JSON.parse(event.data);
  switch (type) {
    case 'text_delta':
      console.log(data.text);  // 流式文本
      break;
    case 'tool_use':
      console.log('Tool:', data.name, data.input);
      break;
    case 'screenshot':
      // data.image 包含 base64 截图
      break;
    case 'done':
      console.log('Agent finished');
      break;
    case 'error':
      console.error('Error:', data.message);
      break;
  }
};

// 取消当前任务
ws.send(JSON.stringify({ type: 'cancel' }));
```

#### VNC WebSocket 代理

```
ws://localhost:8000/ws/vnc
```

双向转发 noVNC WebSocket 流量，支持单端口部署。

---

## 会话配置

`SessionConfig` 完整参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model` | string | `claude-sonnet-4-20250514` | 模型名称 |
| `provider` | string | `anthropic` | 提供商：`anthropic`、`bedrock`、`vertex`、`deepseek` |
| `api_key` | string | `""` | API 密钥（留空则使用环境变量） |
| `tool_version` | string | `computer_use_20251124` | 工具版本 |
| `max_tokens` | int | `16384` | 最大输出 token 数 |
| `only_n_most_recent_images` | int | `3` | 保留最近 N 张截图 |
| `custom_system_prompt` | string | `""` | 自定义系统提示后缀 |
| `thinking_mode` | string | `adaptive` | 思考模式：`adaptive`、`extended`、`off` |
| `thinking_effort` | string | `medium` | 思考投入：`low`、`medium`、`high`、`max` |
| `thinking_budget` | int \| null | `null` | 思考预算（token 数） |
| `token_efficient_tools_beta` | bool | `false` | 启用 token 高效工具 Beta |

---

## 多 Provider 支持

### Anthropic（默认）

```env
API_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-api03-...
```

直接使用 Anthropic API，支持完整的 Computer Use 工具链。

### AWS Bedrock

```env
API_PROVIDER=bedrock
AWS_PROFILE=your-profile
AWS_REGION=us-west-2
```

需要配置 AWS 凭证和 Bedrock 模型访问权限。

### Google Cloud Vertex

```env
API_PROVIDER=vertex
CLOUD_ML_REGION=us-east5
ANTHROPIC_VERTEX_PROJECT_ID=your-project-id
```

需要 GCloud 凭证。

### DeepSeek

```env
API_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

通过 OpenAI 兼容 API 调用。**注意：** DeepSeek 不支持 Computer Use 工具，仅提供基础对话能力。

---

## 数据库

### Schema

**sessions 表：**

| 列 | 类型 | 说明 |
|----|------|------|
| `id` | TEXT (UUID) | 主键 |
| `name` | TEXT | 会话名称 |
| `status` | TEXT | active / completed / error |
| `config_json` | TEXT | JSON 配置 |
| `created_at` | DATETIME | 创建时间（UTC） |
| `updated_at` | DATETIME | 更新时间（UTC） |

**messages 表：**

| 列 | 类型 | 说明 |
|----|------|------|
| `id` | INTEGER (自增) | 主键 |
| `session_id` | TEXT (FK) | 关联会话，级联删除 |
| `role` | TEXT | user / assistant / tool |
| `content_json` | TEXT | JSON 序列化的消息内容 |
| `tool_use_id` | TEXT | 工具调用 ID（可选） |
| `created_at` | DATETIME | 创建时间（UTC） |

### 持久化

数据库文件通过 Docker volume 映射到宿主机：

```
./data/computer_use.db  ←→  /home/computeruse/data/computer_use.db (容器内)
```

容器重启/重建后数据不会丢失。

---

## 并发安全

系统采用三层并发保护机制：

| 层级 | 机制 | 代码位置 | 作用 |
|------|------|----------|------|
| 会话级 | `asyncio.Lock` | `SessionState.lock` | 同一会话的消息处理互斥 |
| 全局级 | `asyncio.Lock` | `SessionManager._global_lock` | 内存字典操作互斥 |
| 运行检查 | `is_running` 属性 | 返回 409 Conflict | 拒绝同一会话的并发请求 |
| 取消机制 | `asyncio.Event` | `cancel_event` | 支持协作取消正在运行的任务 |

每个会话的 agent loop 以独立的 `asyncio.Task` 运行，多个会话可以同时处理而互不干扰。

---

## Docker 部署

### docker-compose.yml 关键配置

```yaml
services:
  computer-use:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"   # FastAPI
      - "6080:6080"   # noVNC
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - API_PROVIDER=${API_PROVIDER:-anthropic}
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY:-}
      - DEEPSEEK_BASE_URL=${DEEPSEEK_BASE_URL:-https://api.deepseek.com}
      - DEEPSEEK_MODEL=${DEEPSEEK_MODEL:-deepseek-chat}
    volumes:
      - ./data:/home/computeruse/data
    restart: unless-stopped
    shm_size: "2gb"
```

### 自定义屏幕分辨率

编辑 `docker-compose.yml` 中的 `build.args`：

```yaml
build:
  args:
    DISPLAY_NUM: 1
    HEIGHT: 768
    WIDTH: 1024
```

建议使用 XGA (1024×768) 以平衡模型精度和性能。

### 常用命令

```bash
# 启动
docker compose up -d

# 重新构建并启动
docker compose up --build -d

# 查看日志
docker compose logs -f

# 停止
docker compose down

# 停止并删除数据卷
docker compose down -v
```

---

## 项目结构

```
computer-use-demo/
├── backend/                     # FastAPI 后端
│   ├── routers/
│   │   ├── sessions.py          # 会话管理 API
│   │   └── ws.py               # WebSocket 路由（事件流 + VNC 代理）
│   ├── services/
│   │   ├── __init__.py          # 会话管理器（并发安全）
│   │   └── sampling.py          # Agent 循环（多 provider 适配）
│   ├── __init__.py
│   ├── config.py               # 应用配置
│   ├── database.py             # SQLAlchemy 模型
│   ├── main.py                 # FastAPI 入口
│   ├── models.py               # Pydantic 模型
│   └── requirements.txt        # Python 依赖
├── computer_use_demo/          # 原始 Computer Use 工具库
│   ├── tools/                  # 工具实现（computer, bash, edit）
│   ├── __init__.py
│   ├── loop.py                 # 原始 Streamlit agent 循环
│   └── requirements.txt
├── static/                     # 前端静态文件
│   ├── index.html              # 前端 SPA
│   ├── app.js                  # 前端逻辑
│   └── style.css               # 样式
├── image/                      # Docker 容器内配置
│   ├── entrypoint.sh           # 容器启动脚本（Xvfb + VNC + noVNC + FastAPI）
│   └── ...
├── data/                       # 持久化数据（数据库文件）
│   └── computer_use.db
├── tests/                      # 测试
├── .env                        # 环境变量（不提交到 Git）
├── docker-compose.yml          # Docker Compose 配置
├── Dockerfile                  # Docker 镜像构建
├── pyproject.toml              # Python 项目配置
└── README.md
```

---

## 开发

### 本地开发

```bash
# 安装依赖
pip install -r backend/requirements.txt
pip install -r computer_use_demo/requirements.txt

# 设置环境变量
export ANTHROPIC_API_KEY=sk-ant-...
export DATABASE_URL=sqlite+aiosqlite:///./data/computer_use.db

# 启动开发服务器
python -m backend.main
```

### 容器内热重载开发

```bash
docker compose up --build -d

# 本地编辑代码后，重建容器：
docker compose up --build -d
```

### 运行测试

```bash
pip install -r test-requirements.txt
pytest tests/
```

---

## 与原版 Streamlit 实现的对比

| 特性 | Streamlit 原版 | FastAPI 新版 |
|------|---------------|-------------|
| 会话管理 | ❌ 单会话 | ✅ 多会话 CRUD |
| 实时流式 | ❌ 轮询 | ✅ WebSocket 推送 |
| 聊天历史 | ❌ 内存 | ✅ SQLite 持久化 |
| 并发 | ❌ 单线程 | ✅ asyncio + 锁 |
| API | ❌ 无 | ✅ REST + WebSocket |
| 前端 | Streamlit 组件 | Vanilla HTML/JS |
| 多 Provider | ✅ | ✅ + DeepSeek |
| Docker | ✅ | ✅ 简化 |
| API 文档 | ❌ | ✅ Swagger UI |

---

## 注意事项

- **Computer Use 是 Beta 功能**：API 可能变化，请关注 [Anthropic 发布说明](https://docs.claude.com/en/release-notes/api)
- **DeepSeek 限制**：DeepSeek 不支持 Computer Use 工具，仅提供对话模式
- **Docker 需要较大内存**：建议至少分配 4GB 内存给 Docker
- **网络依赖**：容器需要访问 API 端点（api.anthropic.com 等）
- **Windows 用户**：确保 Docker Desktop 使用 WSL2 后端，并在 Docker Desktop GUI 中配置镜像加速器

---

## License

本项目基于 [Anthropic Claude Quickstarts](https://github.com/anthropics/claude-quickstarts) 修改，遵循原项目许可证。
