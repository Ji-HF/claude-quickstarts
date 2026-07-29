# Computer Use Demo — 录屏演示解说脚本

> **演示环境**: Windows + Docker Desktop  
> **API 地址**: `http://127.0.0.1:8000` (注意: Windows 上必须用 127.0.0.1 而非 localhost，因为 IPv6 优先级问题)  
> **VNC 地址**: `http://127.0.0.1:6080/vnc.html`  
> **Swagger UI**: `http://127.0.0.1:8000/docs`

---

## 场景一：API 健康检查 & Swagger UI 展示 (约 2 分钟)

**画面**：打开浏览器，展示 Swagger UI 页面

**解说词**：
> "大家好，今天我来演示 Computer Use Demo 项目的核心功能。
> 这是一个基于 FastAPI + Docker 的 AI 电脑操控系统，支持多 LLM 提供商。
> 
> 首先我们打开 Swagger UI —— 这是 FastAPI 自动生成的交互式 API 文档。
> 可以看到所有 API 端点都列在这里，包括会话管理、消息发送、WebSocket 实时通信等。
> 
> 我们先测试健康检查接口 `/api/health`，点击 'Try it out' → 'Execute'。
> 返回 `status: ok`，还有 VNC 端口信息。这说明服务运行正常。
> 
> 我们还可以直接查看 OpenAPI Schema —— `/openapi.json`，
> 这是标准的 OpenAPI 3.0 规范，任何支持 Swagger 的工具都可以导入。"

**操作步骤**：
1. 浏览器打开 `http://127.0.0.1:8000/docs`
2. 展开 GET `/api/health`，点击 Execute
3. 展示返回的 JSON 结果
4. 展示其他 API 端点列表

---

## 场景二：创建会话 → WebSocket 连接 → 发送命令 → 流式响应 (约 3-4 分钟)

**画面**：运行 `test_verify.py` 脚本，展示终端输出

**解说词**：
> "接下来我们演示核心流程：创建会话、建立 WebSocket 连接、发送指令、接收实时流式响应。
> 
> 首先调用 POST `/api/sessions` 创建一个新会话。
> 我们配置 provider 为 deepseek，使用 deepseek-chat 模型。
> 返回 201 Created，会话 ID 和状态都正常。
> 
> 然后我们建立 WebSocket 连接 —— 这是实现实时通信的关键。
> 连接到 `/ws/sessions/{session_id}`，收到 'connected' 确认事件。
> 
> 现在发送一条消息：'你好，请用中文简单介绍一下你自己'
> 通过 POST `/api/sessions/{id}/chat` 发送。
> 返回 `status: accepted`，表示消息已接收，AI 正在处理。
> 
> 重点看终端下方的 WebSocket 事件流 —— 我们收到了 48 个 text_delta 事件，
> 这就是流式响应的效果，每个 delta 是一小段文本，
> 拼起来就是完整的 AI 回复：'你好！我是 DeepSeek，由深度求索公司创造的 AI 助手...'
> 
> 整个过程从发消息到完整回复只用了不到 10 秒。"

**操作步骤**：
1. 终端运行测试脚本（或手动 curl + websocat 演示）
2. 高亮 POST /api/sessions → 201
3. 高亮 WebSocket connected 事件
4. 高亮 POST /chat → 200 accepted
5. 展示 text_delta 事件流和完整回复内容

---

## 场景三：VNC 桌面界面 (约 2-3 分钟)

**画面**：浏览器打开 VNC 页面，展示 Ubuntu 虚拟桌面

**解说词**：
> "这个项目的一大亮点是内置了 VNC 远程桌面。
> 我们打开浏览器访问 port 6080，看到的是一个完整的 Ubuntu 22.04 桌面环境。
> 
> VNC 通过 noVNC 实现，纯 HTML5 不需要任何客户端插件。
> 在这个虚拟桌面里，AI 可以像人类一样操作电脑——
> 移动鼠标、点击按钮、键盘输入、打开应用、浏览网页等等。
> 
> 我们可以看到桌面已经预装了 Firefox 浏览器、LibreOffice、文本编辑器、
> 计算器、画图工具等常用软件。任务栏在底部。
> 
> （可选演示）我们可以手动在这个桌面里操作一下，
> 比如打开一个终端、输入 ls 命令，感受一下真实桌面环境。"

**操作步骤**：
1. 浏览器打开 `http://127.0.0.1:6080/vnc.html`
2. 展示 Ubuntu 桌面完整界面
3. 点击左下角菜单，展示已安装的应用列表
4. （可选）打开终端，运行 `ls /home/computeruse`

---

## 场景四：数据持久化验证 (约 2-3 分钟)

**画面**：终端操作 + 宿主机文件浏览器

**解说词**：
> "数据持久化是企业级应用的关键需求。
> 这个项目使用 SQLite 数据库，通过 Docker volume 挂载到宿主机。
> 
> 我们来验证一下：先创建一个测试会话，名称叫'持久化测试'。
> 通过 GET 请求确认会话已创建成功。
> 
> 关键点来了 —— 数据库文件存储在宿主机的 `data/computer_use.db`，
> 通过 docker-compose.yml 里的 volume 配置挂载。
> 即使容器被删除或重启，数据也不会丢失。
> 
> 我们可以直接查看宿主机上的 SQLite 文件：
> 
> ```
> python -c "
> import sqlite3
> db = sqlite3.connect('data/computer_use.db')
> rows = db.execute('SELECT id, name, status FROM sessions').fetchall()
> for r in rows:
>     print(r)
> "
> ```
> 
> 可以看到刚才创建的会话已经持久化到磁盘了。
> 如果现在重启 Docker 容器，这些数据依然存在。"

**操作步骤**：
1. 终端运行创建会话的 curl 或 Python 命令
2. 展示 GET 查询结果
3. 打开文件浏览器，定位到 `data/computer_use.db`
4. 运行 Python 查询 SQLite，展示持久化的会话记录

---

## 场景五：并发多会话测试 (约 2-3 分钟)

**画面**：运行并发测试脚本，展示终端输出

**解说词**：
> "最后我们测试系统的并发处理能力。
> 同时创建 3 个会话，然后向其中 2 个并发发送消息。
> 
> 看 —— 3 个会话几乎同时创建成功，都是 201。
> 然后我们使用 asyncio.gather 并发发送 2 条消息，
> 每条消息都通过独立的 WebSocket 连接接收流式响应。
> 
> 结果：两个会话都成功收到了 AI 的文本回复。
> 这证明了系统的 WebSocket 管理和 LLM API 调用能够正确处理并发请求。
> 
> 最后我们清理测试数据，删除这 3 个会话。
> 查询会话列表，确认清理成功。"

**操作步骤**：
1. 展示并发创建 3 个会话的输出
2. 展示并发 WebSocket 连接和消息发送
3. 展示两个会话都收到了回复
4. 展示清理后的会话列表

---

## 总结 (约 30 秒)

**解说词**：
> "总结一下，我们今天演示了 Computer Use Demo 的五大核心能力：
> 1. 完整的 RESTful API + Swagger 文档
> 2. WebSocket 实时流式通信
> 3. VNC 远程桌面操控
> 4. SQLite 数据持久化
> 5. 多会话并发处理
> 
> 这个项目展示了如何用 FastAPI + Docker 构建一个
> 生产级的 AI 电脑操控系统。感谢观看！"

---

## 录制准备清单

- [ ] 确保 Docker 容器正在运行: `docker ps | grep computer-use-demo`
- [ ] 浏览器准备 3 个标签页: Swagger UI, VNC, 前端界面
- [ ] 终端准备，已 `cd` 到项目目录
- [ ] 测试脚本可运行: `python test_verify.py`
- [ ] 关闭无关通知和窗口
- [ ] 准备录屏软件 (OBS / 系统自带)

## 快速命令参考

```powershell
# 启动容器
cd D:\workspace\PythonProject\claude-quickstarts\computer-use-demo
docker compose up -d

# 运行完整验证
python test_verify.py

# 单独测试 health
python -c "import httpx; r=httpx.get('http://127.0.0.1:8000/api/health'); print(r.json())"

# 查看容器日志
docker logs computer-use-demo --tail 20

# 查询数据库
python -c "
import sqlite3
db = sqlite3.connect('data/computer_use.db')
for r in db.execute('SELECT id, name, status FROM sessions'):
    print(r)
"
```
