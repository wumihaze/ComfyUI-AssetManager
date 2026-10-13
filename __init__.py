# -*- coding: utf-8 -*-
"""
ComfyUI 资产管理插件
=====================
集成进 ComfyUI 网页的原生 Tab: 浏览/搜索/日历/预览/删除资产,
切换输出目录(重启后自动恢复), 一键备份(资产库+工作流+配置)。
"""

import asyncio
import os
import sys
import threading

# 保证能 import 同目录的核心库
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import assets_core
from prompt_history import PromptHistoryIndex

WEB_DIRECTORY = "web"
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

__version__ = "1.0.4"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_cfg = assets_core.load_config(BASE_DIR)
_arch_default, _ = assets_core.default_asset_dirs(BASE_DIR)
_arch = os.path.abspath(_cfg.get("archive_dir") or _arch_default)
os.makedirs(_arch, exist_ok=True)
_state = assets_core.load_state(_arch)
_LOCK = threading.Lock()
_stop = threading.Event()

# 启动时应用配置的输出目录(实现"重启后自动恢复")
try:
    import folder_paths
    _out = (_cfg.get("output_dir") or "").strip()
    if _out:
        os.makedirs(_out, exist_ok=True)
        folder_paths.set_output_directory(os.path.abspath(_out))
except Exception:
    folder_paths = None


def _current_output_dir():
    if folder_paths is not None:
        try:
            return folder_paths.get_output_directory()
        except Exception:
            pass
    return (_cfg.get("output_dir") or "").strip()


# ---------------------------------------------------------------------------
# 提示词兜底索引: 从 ComfyUI 服务端执行历史按文件名找回 prompt/workflow,
# 解决"文件没内嵌元数据 -> 面板显示未检测到提示词"(外部拖入的图 / --disable-metadata
# / 不写元数据的保存节点)。服务端不可用时自动停用, 不影响插件其它功能。
# ---------------------------------------------------------------------------
_hist = PromptHistoryIndex()


def _prompt_resolver(rel, src):
    """给 assets_core 用的回查函数: 返回 (prompt_graph, workflow_graph) 或 None"""
    _hist.refresh()
    return _hist.lookup(rel, src)


def _watch_loop():
    while not _stop.is_set():
        if _cfg.get("auto_archive", True):
            try:
                out = _current_output_dir()
                if out:
                    with _LOCK:
                        assets_core.scan_all(out, _arch, _state, _cfg, _prompt_resolver)
            except Exception:
                pass
        _stop.wait(float(_cfg.get("interval_sec", 10)))


if _cfg.get("auto_archive", True):
    threading.Thread(target=_watch_loop, daemon=True).start()


# ---------------------------------------------------------------------------
# API 路由 (ComfyUI 会自动同时注册 /asset/xxx 与 /api/asset/xxx)
# ---------------------------------------------------------------------------

from server import PromptServer  # noqa: E402
from aiohttp import web  # noqa: E402


@PromptServer.instance.routes.get("/asset/list")
async def asset_list(request):
    runs = await asyncio.to_thread(assets_core.list_runs, _arch)
    return web.json_response({"ok": True, "count": len(runs), "runs": runs})


@PromptServer.instance.routes.get("/asset/config")
async def asset_config(request):
    _, _bak_default = assets_core.default_asset_dirs(BASE_DIR)
    return web.json_response({
        "ok": True,
        "config": _cfg,
        "archive_dir": _arch,
        "current_output_dir": _current_output_dir(),
        "default_backup_dir": _bak_default,
        "prompt_history": _hist.stats(),
    })


@PromptServer.instance.routes.post("/asset/set_output_dir")
async def asset_set_output_dir(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        return web.json_response({"ok": False, "error": "Request body must be a JSON object"})
    path = body.get("path", "")
    if not isinstance(path, str):
        return web.json_response({"ok": False, "error": "path must be a string"})
    path = path.strip()
    if not path:
        return web.json_response({"ok": False, "error": "Missing output directory path"})
    path = os.path.abspath(path)
    try:
        os.makedirs(path, exist_ok=True)
        if folder_paths is not None:
            folder_paths.set_output_directory(path)
        _cfg["output_dir"] = path
        assets_core.save_config(BASE_DIR, _cfg)
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})
    return web.json_response({"ok": True, "output_dir": path})


@PromptServer.instance.routes.post("/asset/set_config")
async def asset_set_config(request):
    """保存配置(在面板里修改所有设置)。

    安全(修复 Comfy Registry policy-v0.2 ARBITRARY_FILE_LAUNCH):
    请求体**必须经过键白名单**(assets_core.CLIENT_SETTABLE_KEYS)过滤后才能进入 _cfg;
    任何未知键(尤其是 ffprobe/ffmpeg 这类可执行文件解析项)一律拒绝并回报 errors,
    不再出现 `_cfg.update(body)` 这种无过滤合并。
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        return web.json_response({"ok": False, "error": "Request body must be a JSON object"})

    raw = dict(body)
    errors = []
    # 1) 键白名单: 未声明的键直接剔除
    rejected = [k for k in raw.keys() if k not in assets_core.CLIENT_SETTABLE_KEYS]
    if rejected:
        for k in rejected:
            errors.append(f"Config key not allowed: {k}")
    updates = {k: v for k, v in raw.items() if k in assets_core.CLIENT_SETTABLE_KEYS}
    new_arch = None

    # 2) 目录类: 规范化 + 建目录
    for key in ("archive_dir", "backup_dir", "output_dir"):
        if key in updates:
            val = updates[key]
            val = val.strip() if isinstance(val, str) else ""
            if key == "output_dir" and not val:
                updates[key] = ""  # 空=恢复 ComfyUI 默认 output
                continue
            if val:
                val = os.path.abspath(val)
                try:
                    os.makedirs(val, exist_ok=True)
                    updates[key] = val
                except Exception as e:
                    errors.append(f"Cannot create {key}: {e}")
                    updates.pop(key, None)
            else:
                updates.pop(key, None)

    # 3) 数值类: 必须为整数且在合法区间
    for key, (lo, hi) in assets_core.NUMERIC_LIMITS.items():
        if key in updates:
            try:
                v = int(updates[key])
                if v < lo or v > hi:
                    raise ValueError
                updates[key] = v
            except Exception:
                errors.append(f"{key} must be an integer in [{lo}, {hi}]")
                updates.pop(key, None)

    # 4) 布尔类: 只接受真正的 bool(避免字符串 "false" 被 bool() 判成 True)
    for key in ("auto_archive", "archive_existing"):
        if key in updates:
            if isinstance(updates[key], bool):
                pass
            else:
                errors.append(f"{key} must be a boolean")
                updates.pop(key, None)

    global _arch, _state
    with _LOCK:
        _cfg.update(updates)
        assets_core.save_config(BASE_DIR, _cfg)
        if "archive_dir" in updates:
            new_arch = updates["archive_dir"]
            _arch = new_arch
            _state = assets_core.load_state(new_arch)
        if "output_dir" in updates and updates["output_dir"] and folder_paths is not None:
            folder_paths.set_output_directory(updates["output_dir"])

    return web.json_response({
        "ok": True, "config": _cfg, "archive_dir": _arch,
        "current_output_dir": _current_output_dir(), "errors": errors,
    })


@PromptServer.instance.routes.post("/asset/delete")
async def asset_delete(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        return web.json_response({"ok": False, "error": "Request body must be a JSON object"})
    run_id = body.get("run_id")
    if run_id is not None and not isinstance(run_id, str):
        return web.json_response({"ok": False, "error": "run_id must be a string"})

    def _go():
        with _LOCK:
            return assets_core.delete_run(_arch, _current_output_dir(), _state, run_id)

    result = await asyncio.to_thread(_go)
    return web.json_response(result)


@PromptServer.instance.routes.post("/asset/delete_batch")
async def asset_delete_batch(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        return web.json_response({"ok": False, "error": "Request body must be a JSON object"})
    run_ids = body.get("run_ids") or []
    if not isinstance(run_ids, list):
        return web.json_response({"ok": False, "error": "run_ids must be an array"})
    # 只保留字符串元素, 防止非字符串进入路径拼接
    run_ids = [r for r in run_ids if isinstance(r, str)]
    if len(run_ids) > 500:
        return web.json_response({"ok": False, "error": "too many run_ids (max 500)"})

    def _go():
        deleted, failed = 0, []
        with _LOCK:
            for rid in run_ids:
                r = assets_core.delete_run(_arch, _current_output_dir(), _state, rid)
                if r.get("ok"):
                    deleted += 1
                else:
                    failed.append(rid)
        return {"ok": True, "deleted": deleted, "failed": failed}

    result = await asyncio.to_thread(_go)
    return web.json_response(result)


@PromptServer.instance.routes.post("/asset/scan")
async def asset_scan(request):
    # 强制刷新一次服务端提示词索引: 刚跑完的任务要能立刻按文件名找回 prompt
    _hist.refresh(force=True)

    def _go():
        with _LOCK:
            return assets_core.scan_all(_current_output_dir(), _arch, _state, _cfg, _prompt_resolver)

    n = await asyncio.to_thread(_go)
    return web.json_response({"ok": True, "new": n})


@PromptServer.instance.routes.post("/asset/backup")
async def asset_backup(request):
    def _go():
        wdirs = []
        if folder_paths is not None:
            try:
                ud = folder_paths.get_user_directory()
                w = os.path.join(ud, "default", "workflows")
                if os.path.isdir(w):
                    wdirs.append(w)
            except Exception:
                pass
        return assets_core.backup_assets(_cfg, BASE_DIR, wdirs)

    result = await asyncio.to_thread(_go)
    return web.json_response(result)


@PromptServer.instance.routes.get("/asset/file")
async def asset_file(request):
    rel = request.rel_url.query.get("p", "")
    if not isinstance(rel, str):
        return web.Response(status=400, text="bad request")
    p = assets_core.safe_media_path(_arch, rel)
    if not p:
        return web.Response(status=404, text="not found")
    return web.FileResponse(p)


@PromptServer.instance.routes.get("/asset/workflow")
async def asset_workflow(request):
    rel = request.rel_url.query.get("p", "")
    if not isinstance(rel, str):
        return web.Response(status=400, text="bad request")
    p = assets_core.safe_media_path(_arch, rel)
    if not p:
        return web.Response(status=404, text="not found")
    name = os.path.basename(p)
    return web.FileResponse(p, headers={
        "Content-Disposition": f'attachment; filename="{name}"',
    })


def _browsable_roots():
    """允许浏览的目录根(输出/归档/备份目录), 防止浏览任意系统目录"""
    roots = []
    out = _current_output_dir()
    if out:
        roots.append(os.path.abspath(out))
    roots.append(os.path.abspath(_arch))
    bak = (_cfg.get("backup_dir") or "").strip() or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "asset_backups")
    roots.append(os.path.abspath(bak))
    return [r.lower() for r in roots]


def _is_browsable(path):
    """path 必须在允许目录内, 或是某个允许目录的父级链上(用于从盘符导航)"""
    p = os.path.abspath(path).lower()
    if len(p) <= 3:  # 驱动器根, 允许作为起点
        return True
    for r in _browsable_roots():
        if p == r or p.startswith(r + os.sep) or r.startswith(p + os.sep):
            return True
    return False


@PromptServer.instance.routes.get("/asset/browse_dir")
async def asset_browse_dir(request):
    """浏览文件系统目录(供设置里的「浏览…」按钮用), 仅限输出/归档/备份目录及其父级链"""
    import string
    path = request.rel_url.query.get("path", "")
    try:
        if not isinstance(path, str):
            return web.json_response({"ok": False, "error": "path must be a string"})
        if len(path) > 4096:
            return web.json_response({"ok": False, "error": "path too long"})
        if not path:
            drives = [d + ":\\" for d in string.ascii_uppercase if os.path.exists(d + ":\\")]
            return web.json_response({"ok": True, "path": "", "parent": None, "dirs": drives})
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            return web.json_response({"ok": False, "error": "Directory not found"})
        if not _is_browsable(path):
            return web.json_response({"ok": False, "error": "Directory is outside the allowed browse scope"})
        parent = os.path.dirname(path)
        if parent == path:
            parent = None
        dirs = sorted([n for n in os.listdir(path) if os.path.isdir(os.path.join(path, n))])
        return web.json_response({"ok": True, "path": path, "parent": parent, "dirs": dirs})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})
