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

WEB_DIRECTORY = "web"
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

__version__ = "1.0.2"

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


def _watch_loop():
    while not _stop.is_set():
        if _cfg.get("auto_archive", True):
            try:
                out = _current_output_dir()
                if out:
                    with _LOCK:
                        assets_core.scan_all(out, _arch, _state, _cfg)
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
    })


@PromptServer.instance.routes.post("/asset/set_output_dir")
async def asset_set_output_dir(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    path = (body or {}).get("path", "")
    path = (path or "").strip()
    if not path:
        return web.json_response({"ok": False, "error": "缺少输出目录路径"})
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
    """保存配置(在面板里修改所有设置): 支持 output_dir/archive_dir/backup_dir/
    auto_archive/thumb_width/interval_sec/ffprobe/ffmpeg"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    updates = dict(body or {})
    errors = []
    new_arch = None

    # 目录类: 规范化 + 建目录
    for key in ("archive_dir", "backup_dir", "output_dir"):
        if key in updates:
            val = (updates[key] or "").strip()
            if key == "output_dir" and not val:
                updates[key] = ""  # 空=恢复 ComfyUI 默认 output
                continue
            if val:
                val = os.path.abspath(val)
                try:
                    os.makedirs(val, exist_ok=True)
                    updates[key] = val
                except Exception as e:
                    errors.append(f"{key} 无法创建: {e}")
                    updates.pop(key, None)
            else:
                updates.pop(key, None)

    # 数值类
    for key in ("thumb_width", "interval_sec"):
        if key in updates:
            try:
                updates[key] = int(updates[key])
                if updates[key] <= 0:
                    raise ValueError
            except Exception:
                errors.append(f"{key} 必须是正整数")
                updates.pop(key, None)

    if "auto_archive" in updates:
        updates["auto_archive"] = bool(updates["auto_archive"])

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
    run_id = (body or {}).get("run_id")

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
    run_ids = (body or {}).get("run_ids") or []
    if not isinstance(run_ids, list):
        return web.json_response({"ok": False, "error": "run_ids 必须是数组"})

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
    def _go():
        with _LOCK:
            return assets_core.scan_all(_current_output_dir(), _arch, _state, _cfg)

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
    p = assets_core.safe_media_path(_arch, rel)
    if not p:
        return web.Response(status=404, text="not found")
    return web.FileResponse(p)


@PromptServer.instance.routes.get("/asset/workflow")
async def asset_workflow(request):
    rel = request.rel_url.query.get("p", "")
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
        if not path:
            drives = [d + ":\\" for d in string.ascii_uppercase if os.path.exists(d + ":\\")]
            return web.json_response({"ok": True, "path": "", "parent": None, "dirs": drives})
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            return web.json_response({"ok": False, "error": "目录不存在"})
        if not _is_browsable(path):
            return web.json_response({"ok": False, "error": "该目录不在允许浏览范围内"})
        parent = os.path.dirname(path)
        if parent == path:
            parent = None
        dirs = sorted([n for n in os.listdir(path) if os.path.isdir(os.path.join(path, n))])
        return web.json_response({"ok": True, "path": path, "parent": parent, "dirs": dirs})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})
