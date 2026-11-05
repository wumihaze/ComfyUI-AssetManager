"""HTTP 层安全冒烟: 把插件的路由挂到一个独立 aiohttp 服务上跑真请求。

不启动 ComfyUI、不加载模型、不启动后台监视线程, 归档目录指向临时目录,
所以不会碰到真实数据。验证的是 aiohttp 真实行为: 状态码、响应头、
FileResponse、query 解析、Origin 判定。

用法: python tests/http_smoke.py      (需要 aiohttp, ComfyUI 已自带)
"""

import asyncio
import json
import os
import sys
import tempfile
import threading
import time
import types
import urllib.error
import urllib.request
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_DIR))

import assets_core

def _free_port():
    """占一个空闲端口再放掉, 避免和本机已开的服务撞车。"""
    import socket
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


PORT = _free_port()
BASE = "http://127.0.0.1:%d" % PORT
OK = []
BAD = []


def check(name, cond, detail=""):
    (OK if cond else BAD).append(name + ("" if cond else "  <<< " + str(detail)))


class Routes:
    def __init__(self):
        self.items = []

    def _reg(self, method):
        def deco(path):
            def wrap(fn):
                self.items.append((method, path, fn))
                return fn
            return wrap
        return deco

    def get(self, path):
        return self._reg("GET")(path)

    def post(self, path):
        return self._reg("POST")(path)


def import_plugin(archive_dir, output_dir):
    routes = Routes()
    server = types.ModuleType("server")
    server.PromptServer = types.SimpleNamespace(
        instance=types.SimpleNamespace(routes=routes))
    fp = types.ModuleType("folder_paths")
    fp.get_output_directory = lambda: str(output_dir)
    fp.set_output_directory = lambda p: None
    fp.get_user_directory = lambda: str(Path(archive_dir) / "user")
    sys.modules["server"] = server
    sys.modules["folder_paths"] = fp

    cfg = dict(assets_core.DEFAULT_CONFIG)
    cfg.update({"archive_dir": str(archive_dir),
                "backup_dir": str(Path(archive_dir) / "bak"),
                "output_dir": str(output_dir)})
    real_load = assets_core.load_config
    assets_core.load_config = lambda base: dict(cfg)
    # 别让任何走通的写配置路径改到插件目录里的真实 config.json
    real_save = assets_core.save_config
    assets_core.save_config = lambda *a, **k: None

    real_thread = threading.Thread

    class _NoThread:
        def __init__(self, *a, **k):
            pass

        def start(self):
            pass

    threading.Thread = _NoThread
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "asset_manager_plugin_http", str(PLUGIN_DIR / "__init__.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        threading.Thread = real_thread
        assets_core.load_config = real_load
        assets_core.save_config = real_save
    return mod, routes


def request(method, path, body=None, origin=None, host=None):
    url = BASE + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if origin:
        headers["Origin"] = origin
    if host:
        headers["Host"] = host
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            raw = r.read()
            return r.status, dict(r.headers), raw
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def json_of(raw):
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return None


def main():
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    arch, out = root / "archive", root / "output"
    arch.mkdir()
    out.mkdir()

    # 造一条真实归档记录, 供 /asset/file 使用
    run = arch / "2026-11-05" / "run-1"
    run.mkdir(parents=True)
    (run / "info.json").write_text(json.dumps({
        "run_id": "run-1", "generated_at": "2026-11-05T10:00:00",
        "source_rel": "角色/图.png", "media": "图.png", "kind": "image",
        "thumb": "thumb.jpg", "has_workflow": True,
    }, ensure_ascii=False), encoding="utf-8")
    (run / "图.png").write_bytes(b"\x89PNG\r\n\x1a\nreal-bytes")
    (run / "thumb.jpg").write_bytes(b"thumb")
    (run / "workflow.json").write_text("{}", encoding="utf-8")
    (arch / "archive_state.json").write_text("{}", encoding="utf-8")

    mod, routes = import_plugin(arch, out)
    mod._arch = str(arch)

    async def serve():
        from aiohttp import web
        app = web.Application()
        for method, path, fn in routes.items:
            app.router.add_route(method, path, fn)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", PORT)
        await site.start()
        return runner

    loop = asyncio.new_event_loop()
    runner_holder = {}

    def run_loop():
        asyncio.set_event_loop(loop)
        runner_holder["r"] = loop.run_until_complete(serve())
        loop.run_forever()

    th = threading.Thread(target=run_loop, daemon=True)
    th.start()
    for _ in range(50):
        try:
            urllib.request.urlopen(BASE + "/asset/categories", timeout=1)
            break
        except Exception:
            time.sleep(0.1)

    try:
        # ---- 基本可用 ----
        s, h, raw = request("GET", "/asset/categories")
        check("GET /asset/categories 200", s == 200, s)
        check("categories 是 JSON", json_of(raw) is not None, raw[:80])

        # ---- CSRF: 跨站写请求 ----
        s, h, raw = request("POST", "/asset/category", {"action": "create", "name": "CSRF"},
                            origin="https://evil.example")
        check("跨站 create → 403", s == 403, s)
        check("跨站响应体是结构化 JSON", (json_of(raw) or {}).get("ok") is False, raw[:80])
        s, _, raw = request("POST", "/asset/scan", {}, origin="https://evil.example")
        check("跨站 scan → 403", s == 403, s)
        s, _, raw = request("POST", "/asset/set_config", {"archive_dir": str(arch)},
                            origin="http://evil.example")
        check("跨站 set_config → 403", s == 403, s)
        check("跨站请求没有创建分类",
              json_of(request("GET", "/asset/categories")[2])["categories"] == [], "分类被创建了")

        # ---- 同源 / 非浏览器请求放行 ----
        s, _, raw = request("POST", "/asset/category", {"action": "create", "name": "同源"},
                            origin=BASE, host="127.0.0.1:%d" % PORT)
        check("同源 create → 200", s == 200 and (json_of(raw) or {}).get("ok") is True, raw[:120])
        s, _, raw = request("POST", "/asset/category", {"action": "create", "name": "无来源"})
        check("无 Origin(脚本) → 200", s == 200 and (json_of(raw) or {}).get("ok") is True, raw[:120])

        # ---- move / pin 走真 HTTP ----
        cats = json_of(request("GET", "/asset/categories")[2])["categories"]
        check("两个分类都在", len(cats) == 2, cats)
        first, second = cats[0]["id"], cats[1]["id"]
        s, _, raw = request("POST", "/asset/category", {"action": "pin", "id": second, "pinned": True})
        d = json_of(raw)
        check("pin 生效", s == 200 and d["ok"] and d["categories"][0]["id"] == second, raw[:150])
        s, _, raw = request("POST", "/asset/category", {"action": "pin", "id": second, "pinned": "yes"})
        check("pinned 非 bool 被拒", json_of(raw)["ok"] is False, raw[:120])
        s, _, raw = request("POST", "/asset/category", {"action": "move", "id": first, "direction": "up"})
        check("move 生效", json_of(raw)["ok"] is True, raw[:120])
        s, _, raw = request("POST", "/asset/category", {"action": "move", "id": first, "direction": "侧"})
        check("非法 direction 被拒", json_of(raw)["ok"] is False, raw[:120])

        # ---- /asset/file: 只服务清单内的文件 ----
        s, h, raw = request("GET", "/asset/file?p=" + urllib.parse.quote("2026-11-05/run-1/图.png"))
        check("正常媒体 200", s == 200, s)
        check("正常媒体内容正确", raw == b"\x89PNG\r\n\x1a\nreal-bytes", raw[:40])
        check("Content-Type 是图片", (h.get("Content-Type") or "").startswith("image/"), h.get("Content-Type"))

        for bad in ("../../../Windows/win.ini", "C:/Windows/win.ini",
                    "2026-11-05/run-1/info.json", "archive_state.json",
                    "2026-11-05/run-1/../run-1/图.png", ""):
            s, _, raw = request("GET", "/asset/file?p=" + urllib.parse.quote(bad))
            check("穿越/越权被拒: %r" % bad, s == 404, s)

        # ---- /asset/note: 手动备注 ----
        info_file = run / "info.json"
        media_file = run / "图.png"
        media_before = media_file.read_bytes()
        info_before = info_file.read_bytes()

        s, _, raw = request("POST", "/asset/note", {"run_id": "2026-11-05/run-1", "note": "跨站"},
                            origin="https://evil.example")
        check("跨站 note → 403", s == 403, s)
        check("跨站 note 没改 info.json", info_file.read_bytes() == info_before, "文件被改了")

        s, _, raw = request("POST", "/asset/note", {"run_id": "2026-11-05/run-1", "note": "网图 · 蓝调夜景"},
                            origin=BASE, host="127.0.0.1:%d" % PORT)
        d = json_of(raw)
        check("同源 note → 200 ok", s == 200 and d["ok"] is True, raw[:120])
        check("note 回显正确", d.get("note") == "网图 · 蓝调夜景", d)
        saved = json.loads(info_file.read_text(encoding="utf-8"))
        check("info.json 写入 note", saved.get("note") == "网图 · 蓝调夜景", saved.get("note"))
        check("info.json 写入 note_updated_at", bool(saved.get("note_updated_at")), saved)
        check("原字段未被破坏", saved.get("source_rel") == "角色/图.png", saved)
        check("媒体文件未被改动", media_file.read_bytes() == media_before, "媒体被改了")

        runs = json_of(request("GET", "/asset/list")[2])["runs"]
        check("GET /asset/list 带出 note",
              len(runs) == 1 and runs[0].get("note") == "网图 · 蓝调夜景", runs)

        s, _, raw = request("POST", "/asset/note", {"run_id": "2026-11-05/run-1", "note": "x" * 501})
        check("501 字被拒", json_of(raw)["ok"] is False, raw[:120])
        check("超长被拒后 note 不变",
              json.loads(info_file.read_text(encoding="utf-8")).get("note") == "网图 · 蓝调夜景", "被改了")
        s, _, raw = request("POST", "/asset/note", {"run_id": "2026-11-05/run-1", "note": 42})
        check("非字符串 note 被拒", json_of(raw)["ok"] is False, raw[:120])
        s, _, raw = request("POST", "/asset/note", {"run_id": 42, "note": "x"})
        check("非字符串 run_id 被拒", json_of(raw)["ok"] is False, raw[:120])

        s, _, raw = request("POST", "/asset/note",
                            {"run_id": "2026-11-05/../../etc", "note": "x"})
        d = json_of(raw)
        check("穿越 run_id 被拒", d["ok"] is False, raw[:120])
        check("穿越错误信息不含路径", str(root) not in json.dumps(d), d)

        s, _, raw = request("POST", "/asset/note", {"run_id": "2026-11-05/run-1", "note": ""})
        check("空串清除 note", json_of(raw)["ok"] is True, raw[:120])
        check("清除后 info.json 无 note 字段",
              "note" not in json.loads(info_file.read_text(encoding="utf-8")), "字段还在")
        check("清除后媒体文件仍完好", media_file.read_bytes() == media_before, "媒体被改了")

        # 备注里的标记符号原样存, 不在后端做转义(前端用 textContent 渲染)
        s, _, raw = request("POST", "/asset/note",
                            {"run_id": "2026-11-05/run-1", "note": "<b>&amp;</b>\n第二行"})
        check("标记符号与换行原样存",
              json_of(raw).get("note") == "<b>&amp;</b>\n第二行", json_of(raw))

        # ---- /asset/set_output_dir: 建目录失败时不回显路径 ----
        blocker = root / "blocker"
        blocker.write_text("x", encoding="utf-8")
        s, _, raw = request("POST", "/asset/set_output_dir", {"path": str(blocker / "sub")})
        d = json_of(raw)
        check("set_output_dir 失败 → ok:false", s == 200 and d["ok"] is False, raw[:120])
        check("set_output_dir 错误信息不含路径", str(root) not in json.dumps(d), d)
        check("set_output_dir 失败文案固定", d.get("error") == "Cannot switch output directory", d)

        # ---- 写接口在坏归档目录下不 500 ----
        real = mod._arch
        mod._arch = str(root / "nope" / "deeper")
        s, _, raw = request("POST", "/asset/category", {"action": "create", "name": "坏目录"})
        d = json_of(raw)
        check("坏归档目录 → 200 且 ok:false", s == 200 and d["ok"] is False, raw[:120])
        check("错误信息不含路径", str(root) not in json.dumps(d), d)
        mod._arch = real

        # ---- scan 路由 ----
        s, _, raw = request("POST", "/asset/scan", {})
        d = json_of(raw)
        check("scan 返回 JSON", s == 200 and d.get("ok") is True, raw[:120])

        # ---- 未知 action ----
        s, _, raw = request("POST", "/asset/category", {"action": "rm -rf"})
        check("未知 action → ok:false", json_of(raw)["ok"] is False, raw[:120])

    finally:
        loop.call_soon_threadsafe(lambda: runner_holder["r"].cleanup())
        time.sleep(0.3)
        loop.call_soon_threadsafe(loop.stop)
        td.cleanup()

    print("\n".join("  ✔ " + n for n in OK))
    if BAD:
        print("\n".join("  ✘ " + n for n in BAD))
        print("\n%d passed, %d FAILED" % (len(OK), len(BAD)))
        return 1
    print("\nall %d checks passed" % len(OK))
    return 0


if __name__ == "__main__":
    import urllib.parse  # noqa: E402
    raise SystemExit(main())
