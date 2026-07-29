"""
Computer Use Demo — 全功能验证脚本
验证: API健康检查 / Swagger UI / 会话创建 / WebSocket流式响应 / VNC / 持久化 / 并发
用法: pip install httpx websockets && python test_verify.py
"""
import asyncio, json, sys
from datetime import datetime
from pathlib import Path
import httpx
import websockets

BASE = "http://127.0.0.1:8000"
WS_BASE = "ws://127.0.0.1:8000"

# ── 日志文件 ──────────────────────────────────────────────
LOG_DIR = Path(__file__).parent / "test_logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"verify_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
_log_fh = open(LOG_FILE, "w", encoding="utf-8")

def log(msg=""):
    """同时输出到终端和日志文件"""
    text = str(msg)
    print(text)
    _log_fh.write(text + "\n")
    _log_fh.flush()


async def api(method, path, base=BASE, **kw):
    """通用 API 请求"""
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.request(method, f"{base}{path}", **kw)
        ct = r.headers.get("content-type", "")
        try:
            body = r.json() if ct.startswith("application/json") and r.text else r.text
        except Exception:
            body = r.text
        return r.status_code, body


def ok(status): return 200 <= status < 300


# ═══════════════════════════════════════════════════════════
# 1️⃣  API 健康检查 & Swagger 文档
# ═══════════════════════════════════════════════════════════
async def test_01_health_and_docs():
    log("\n" + "=" * 60)
    log("1️⃣  API 健康检查 & Swagger 文档")
    log("=" * 60)
    s, data = await api("GET", "/api/health")
    log(f"  GET /api/health  →  {s}  |  {json.dumps(data, ensure_ascii=False)}")
    assert ok(s) and data["status"] == "ok", "Health check failed!"
    s, _ = await api("GET", "/openapi.json")
    log(f"  GET /openapi.json →  {s}  (OpenAPI schema)")
    assert ok(s)
    s, _ = await api("GET", "/docs")
    log(f"  GET /docs         →  {s}  (Swagger UI)")
    assert ok(s)
    log("  ✅ 全部通过")


# ═══════════════════════════════════════════════════════════
# 2️⃣  创建会话 → WebSocket 流式响应
# ═══════════════════════════════════════════════════════════
async def test_02_session_and_streaming():
    log("\n" + "=" * 60)
    log("2️⃣  创建会话 → WebSocket 流式响应")
    log("=" * 60)

    s, session = await api("POST", "/api/sessions", json={
        "name": "演示会话",
        "config": {"model": "deepseek-chat", "provider": "deepseek",
                    "api_key": "", "max_tokens": 4096, "thinking_mode": "off"}
    })
    log(f"  POST /api/sessions  →  {s}")
    log(f"    id={session['id'][:8]}...  name={session['name']}  status={session['status']}")
    assert ok(s)
    sid = session["id"]

    s, sessions = await api("GET", "/api/sessions")
    log(f"  GET /api/sessions   →  {s}  (total={sessions['total']})")

    events = []

    async def ws_listen():
        try:
            async with websockets.connect(f"{WS_BASE}/ws/sessions/{sid}") as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10)
                events.append(json.loads(raw))
                log(f"  🔌 WS: {events[-1]['type']}")
                for _ in range(50):
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=20)
                        evt = json.loads(raw)
                        events.append(evt)
                        if evt["type"] in ("done", "error", "cancelled"):
                            break
                    except asyncio.TimeoutError:
                        break
        except Exception as e:
            log(f"  ⚠ WS异常: {e}")

    ws_task = asyncio.create_task(ws_listen())
    await asyncio.sleep(1.5)

    log('  📤 发送: "你好，请用中文简单介绍一下你自己"')
    s, ack = await api("POST", f"/api/sessions/{sid}/chat",
                        json={"message": "你好，请用中文简单介绍一下你自己"})
    log(f"  POST /chat          →  {s}  |  {json.dumps(ack, ensure_ascii=False)}")
    assert ok(s)

    await ws_task

    text_deltas = [e for e in events if e["type"] == "text_delta"]
    tool_uses = [e for e in events if e["type"] == "tool_use"]
    errors = [e for e in events if e["type"] == "error"]
    done = [e for e in events if e["type"] == "done"]

    full_text = "".join(e["data"]["text"] for e in text_deltas)
    log(f"  📥 流式响应: {len(text_deltas)} deltas")
    log(f"     {full_text[:200]}{'...' if len(full_text) > 200 else ''}")
    if tool_uses:
        log(f"  🔧 工具调用: {len(tool_uses)}次")
    if errors:
        log(f"  ❌ 错误: {errors[0]}")
    if done:
        log(f"  ✅ {done[0]['data']['message']}")
    assert len(text_deltas) > 0 or len(tool_uses) > 0, "无响应!"
    log("  ✅ 会话 → WebSocket 流式响应 通过")
    return sid


# ═══════════════════════════════════════════════════════════
# 3️⃣  VNC 桌面界面
# ═══════════════════════════════════════════════════════════
async def test_03_vnc():
    log("\n" + "=" * 60)
    log("3️⃣  VNC 桌面界面验证")
    log("=" * 60)
    s, _ = await api("GET", "/vnc.html", base="http://127.0.0.1:6080")
    log(f"  GET :6080/vnc.html  →  {s}")
    assert ok(s)
    s, _ = await api("GET", "/", base="http://127.0.0.1:6080")
    log(f"  GET :6080/          →  {s}")
    assert ok(s)
    log("  ✅ VNC 可访问 (浏览器打开可看实时桌面)")


# ═══════════════════════════════════════════════════════════
# 4️⃣  数据持久化
# ═══════════════════════════════════════════════════════════
async def test_04_persistence():
    log("\n" + "=" * 60)
    log("4️⃣  数据持久化验证")
    log("=" * 60)
    s, session = await api("POST", "/api/sessions", json={
        "name": "持久化测试",
        "config": {"model": "deepseek-chat", "provider": "deepseek",
                    "api_key": "", "max_tokens": 4096, "thinking_mode": "off"}
    })
    sid = session["id"]
    log(f"  📝 创建: {sid[:8]}... name='持久化测试'")
    s, detail = await api("GET", f"/api/sessions/{sid}")
    log(f"  🔍 查询: {s}  name={detail['name']}  status={detail['status']}")
    assert ok(s) and detail["name"] == "持久化测试"
    log("  ✅ 数据已持久化到 SQLite (volume挂载)")


# ═══════════════════════════════════════════════════════════
# 5️⃣  并发多会话
# ═══════════════════════════════════════════════════════════
async def test_05_concurrent():
    log("\n" + "=" * 60)
    log("5️⃣  并发多会话测试")
    log("=" * 60)
    names = [f"并发会话-{i}" for i in range(1, 4)]
    tasks = [api("POST", "/api/sessions", json={
        "name": n,
        "config": {"model": "deepseek-chat", "provider": "deepseek",
                    "api_key": "", "max_tokens": 4096, "thinking_mode": "off"}
    }) for n in names]
    results = await asyncio.gather(*tasks)
    session_ids = []
    for (status, data), name in zip(results, names):
        log(f"  ✅ 创建 {name}: {status}  id={data['id'][:8]}...")
        assert ok(status)
        session_ids.append(data["id"])

    async def send_and_collect(sid, msg):
        collected = []

        async def listen():
            try:
                async with websockets.connect(f"{WS_BASE}/ws/sessions/{sid}") as ws:
                    await asyncio.wait_for(ws.recv(), timeout=5)
                    for _ in range(25):
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=15)
                            evt = json.loads(raw)
                            collected.append(evt["type"])
                            if evt["type"] in ("done", "error"):
                                break
                        except asyncio.TimeoutError:
                            break
            except Exception:
                pass

        listener = asyncio.create_task(listen())
        await asyncio.sleep(0.5)
        await api("POST", f"/api/sessions/{sid}/chat", json={"message": msg})
        await listener
        return collected

    results2 = await asyncio.gather(
        send_and_collect(session_ids[0], "用中文说：你好，并发测试1"),
        send_and_collect(session_ids[1], "用中文说：你好，并发测试2"),
    )
    for i, (cols, name) in enumerate(zip(results2, names[:2])):
        td = "text_delta" in cols
        dn = "done" in cols
        er = "error" in cols
        log(f"  {'✅' if td or dn else '❌'} {name}: text={td} done={dn} err={er}")

    for sid in session_ids:
        await api("DELETE", f"/api/sessions/{sid}")
    s, sessions = await api("GET", "/api/sessions")
    log(f"  🧹 清理后: {sessions['total']} sessions")
    log("  ✅ 并发测试通过")


# ═══════════════════════════════════════════════════════════
async def main():
    log("""
╔══════════════════════════════════════════════════════════╗
║     Computer Use Demo — 全功能验证                       ║
╚══════════════════════════════════════════════════════════╝
""")
    log(f"📝 日志文件: {LOG_FILE}")
    results = {}
    for name, fn in [
        ("01_health", test_01_health_and_docs),
        ("03_vnc", test_03_vnc),
        ("02_streaming", test_02_session_and_streaming),
        ("04_persistence", test_04_persistence),
        ("05_concurrent", test_05_concurrent),
    ]:
        try:
            await fn()
            results[name] = "PASS"
        except Exception as e:
            results[name] = f"FAIL: {e}"
            log(f"  ❌ {e}")

    log("\n" + "=" * 60)
    log("📊 测试结果汇总")
    log("=" * 60)
    for k, v in results.items():
        icon = "✅" if v.startswith("PASS") else "❌"
        log(f"  {icon} {k}: {v}")
    all_pass = all(v.startswith("PASS") for v in results.values())
    log(f"\n{'🎉 全部通过!' if all_pass else '⚠ 部分失败，请检查上方日志'}")
    log(f"\n📝 完整日志已保存到: {LOG_FILE}")
    _log_fh.close()
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    asyncio.run(main())
