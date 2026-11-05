# -*- coding: utf-8 -*-
"""
ComfyUI 资产管理插件
=====================
集成进 ComfyUI 网页的原生 Tab: 浏览/搜索/日历/预览/删除资产,
切换输出目录(重启后自动恢复), 一键备份(资产库+工作流+配置)。
"""

import asyncio
import functools
import mimetypes
import os
import sys
import tempfile
import threading
import urllib.parse

# 保证能 import 同目录的核心库
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import assets_core
from prompt_history import PromptHistoryIndex

WEB_DIRECTORY = "web"
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

__version__ = "1.0.13"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_cfg = assets_core.load_config(BASE_DIR)
_arch_default, _bak_default = assets_core.default_asset_dirs(BASE_DIR)
_startup_warnings = []

# 目录一律按运行时推导: 默认相对 ComfyUI 安装目录, 盘符/安装位置由实际部署决定。
# 配置里若残留其它机器或已移除盘符的路径, 自动回退到默认目录而不是让插件加载失败。
_configured_arch = (_cfg.get("archive_dir") or "").strip()
_arch_candidate = os.path.abspath(_configured_arch) if _configured_arch else _arch_default
_arch = assets_core.ensure_dir(
    _arch_candidate,
    _arch_default,
    os.path.join(os.path.expanduser("~"), ".comfyui-asset-archive"),
    os.path.join(tempfile.gettempdir(), "comfyui_asset_archive"),
)
if not _arch:
    raise RuntimeError("ComfyUI-AssetManager: no writable archive directory available")
if _configured_arch and os.path.normcase(os.path.abspath(_configured_arch)) != os.path.normcase(_arch):
    _startup_warnings.append(
        f"Configured archive directory is unavailable, using {_arch}")
_state = assets_core.load_state(_arch)
_LOCK = threading.Lock()
_stop = threading.Event()

# 启动时应用配置的输出目录(实现"重启后自动恢复")
try:
    import folder_paths
except Exception:
    folder_paths = None

if folder_paths is not None:
    _out = (_cfg.get("output_dir") or "").strip()
    if _out:
        _usable_out = assets_core.ensure_dir(os.path.abspath(_out))
        if _usable_out:
            try:
                folder_paths.set_output_directory(_usable_out)
                _cfg["output_dir"] = _usable_out
            except Exception:
                _startup_warnings.append(f"Cannot switch output directory to {_usable_out}")
        else:
            # 目录不可用: 清空配置, 让 ComfyUI 继续用自己探测到的默认 output
            _cfg["output_dir"] = ""
            _startup_warnings.append(f"Configured output directory is unavailable: {_out}")


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


def _is_cross_origin(request):
    """跨站写请求判定。

    ComfyUI 默认只监听回环, 但浏览器允许任意网页向 127.0.0.1 发"简单请求"
    (text/plain 的表单/fetch), 不需要 CORS 预检就能打到这些写接口。浏览器对
    跨站 POST 一定会带 Origin, 而页面脚本没法伪造它, 所以按 Origin 拦一道。

    只拦真正的 http(s) 跨站来源: 没有 Origin(命令行/脚本)、`Origin: null`
    (file:// 页面)或 app:// 之类的非 http 来源一律放行, 避免误伤桌面端和
    反向代理场景。
    """
    origin = request.headers.get("Origin")
    if not origin:
        return False
    try:
        parsed = urllib.parse.urlparse(origin)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    return parsed.netloc.lower() != (request.headers.get("Host") or "").lower()


def _same_origin_only(handler):
    """给写接口加一道跨站来源校验。"""
    @functools.wraps(handler)
    async def wrapper(request):
        if _is_cross_origin(request):
            return web.json_response(
                {"ok": False, "error": "Cross-origin request rejected"}, status=403)
        return await handler(request)
    return wrapper


@PromptServer.instance.routes.get("/asset/list")
async def asset_list(request):
    runs = await asyncio.to_thread(assets_core.list_runs, _arch)
    return web.json_response({"ok": True, "count": len(runs), "runs": runs})


@PromptServer.instance.routes.get("/asset/config")
async def asset_config(request):
    return web.json_response({
        "ok": True,
        "config": _cfg,
        "archive_dir": _arch,
        "current_output_dir": _current_output_dir(),
        "default_backup_dir": _bak_default,
        "warnings": list(_startup_warnings),
        "prompt_history": _hist.stats(),
    })


@PromptServer.instance.routes.post("/asset/set_output_dir")
@_same_origin_only
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
    _, default_backup = assets_core.default_asset_dirs(BASE_DIR)
    backup_value = _cfg.get("backup_dir")
    backup_dir = backup_value.strip() if isinstance(backup_value, str) and backup_value.strip() else default_backup
    if assets_core.paths_overlap(path, _arch) or assets_core.paths_overlap(path, backup_dir):
        return web.json_response({"ok": False, "error": "Output directory must not overlap archive or backup directory"}, status=400)
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
@_same_origin_only
async def asset_set_config(request):
    """保存配置(在面板里修改所有设置)。

    安全(修复 Comfy Registry policy-v0.5 command-injection):
    请求体**必须经过键白名单**(assets_core.CLIENT_SETTABLE_KEYS)过滤后才能进入 _cfg;
    任何未知键一律拒绝并回报 errors, 不再出现 `_cfg.update(body)` 这种无过滤合并。
    """
    global _arch, _state
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

    # 2) 目录类: 规范化后，禁止输出/归档/备份目录互相包含，避免
    # 扫描递归归档、备份把自身纳入 ZIP，以及目录边界意外扩大。
    for key in ("archive_dir", "backup_dir", "output_dir"):
        if key not in updates:
            continue
        val = updates[key].strip() if isinstance(updates[key], str) else ""
        if key == "output_dir" and not val:
            updates[key] = ""  # 空 = ComfyUI 默认 output
        elif val:
            updates[key] = os.path.abspath(val)
        else:
            updates.pop(key, None)

    _arch_default, _bak_default = assets_core.default_asset_dirs(BASE_DIR)
    output_candidate = updates.get("output_dir") or _current_output_dir()
    archive_candidate = updates.get("archive_dir") or _arch or _arch_default
    backup_candidate = updates.get("backup_dir") or _cfg.get("backup_dir") or _bak_default
    dir_candidates = {
        "output_dir": output_candidate,
        "archive_dir": archive_candidate,
        "backup_dir": backup_candidate,
    }
    conflicts = set()
    keys = tuple(dir_candidates)
    for i, key_a in enumerate(keys):
        for key_b in keys[i + 1:]:
            path_a, path_b = dir_candidates[key_a], dir_candidates[key_b]
            if path_a and path_b and assets_core.paths_overlap(path_a, path_b):
                errors.append(f"{key_a} and {key_b} must not overlap")
                if key_a in updates:
                    conflicts.add(key_a)
                if key_b in updates:
                    conflicts.add(key_b)
    for key in conflicts:
        updates.pop(key, None)

    for key in ("archive_dir", "backup_dir", "output_dir"):
        val = updates.get(key)
        if val:
            try:
                os.makedirs(val, exist_ok=True)
            except Exception:
                # 不回显异常文本(OSError 的 str() 里带绝对路径)
                errors.append(f"Cannot create {key}")
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
@_same_origin_only
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
@_same_origin_only
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


# ---------------------------------------------------------------------------
# 分类: 我的分类(手动) / 归档到分类
# ---------------------------------------------------------------------------

@PromptServer.instance.routes.get("/asset/categories")
async def asset_categories(request):
    data = await asyncio.to_thread(assets_core.load_categories, _arch)
    return web.json_response({"ok": True, "categories": data["categories"]})


@PromptServer.instance.routes.post("/asset/category")
@_same_origin_only
async def asset_category(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        return web.json_response({"ok": False, "error": "Request body must be a JSON object"})
    action = body.get("action")
    name = body.get("name")
    category_id = body.get("id")
    parent = body.get("parent")
    direction = body.get("direction")
    pinned = body.get("pinned")
    if category_id is not None and not isinstance(category_id, str):
        return web.json_response({"ok": False, "error": "id must be a string"})
    if name is not None and not isinstance(name, str):
        return web.json_response({"ok": False, "error": "name must be a string"})
    if parent is not None and not isinstance(parent, str):
        return web.json_response({"ok": False, "error": "parent must be a string"})
    if direction is not None and not isinstance(direction, str):
        return web.json_response({"ok": False, "error": "direction must be a string"})
    if pinned is not None and not isinstance(pinned, bool):
        return web.json_response({"ok": False, "error": "pinned must be a boolean"})

    def _go():
        try:
            with _LOCK:
                if action == "create":
                    return assets_core.create_category(_arch, name, parent)
                if action == "rename":
                    return assets_core.rename_category(_arch, category_id, name)
                if action == "delete":
                    return assets_core.delete_category(_arch, category_id)
                if action == "move":
                    return assets_core.move_category(_arch, category_id, direction)
                if action == "pin":
                    if pinned is None:
                        return {"ok": False, "error": "pinned must be a boolean"}
                    return assets_core.set_category_pinned(_arch, category_id, pinned)
                return {"ok": False, "error": "Unknown action"}
        except Exception:  # 归档目录不可写/不存在时不要抛 500
            # 不把异常文本回给前端: OSError 的 str() 里带绝对路径
            return {"ok": False, "error": "Category operation failed"}

    result = await asyncio.to_thread(_go)
    return web.json_response(result)


@PromptServer.instance.routes.post("/asset/assign")
@_same_origin_only
async def asset_assign(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        return web.json_response({"ok": False, "error": "Request body must be a JSON object"})
    run_ids = body.get("run_ids") or []
    if not isinstance(run_ids, list):
        return web.json_response({"ok": False, "error": "run_ids must be an array"})
    run_ids = [r for r in run_ids if isinstance(r, str)]
    if len(run_ids) > 500:
        return web.json_response({"ok": False, "error": "too many run_ids (max 500)"})
    category = body.get("category")
    if category is not None and not isinstance(category, str):
        return web.json_response({"ok": False, "error": "category must be a string or null"})

    def _go():
        try:
            with _LOCK:
                return assets_core.assign_category(_arch, run_ids, category)
        except Exception:  # 同上: 失败也返回结构化 JSON
            return {"ok": False, "error": "Assign failed"}

    result = await asyncio.to_thread(_go)
    return web.json_response(result)


@PromptServer.instance.routes.post("/asset/note")
@_same_origin_only
async def asset_note(request):
    """写/清一条产物的手动备注(只改 info.json 的 note 字段)。"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        return web.json_response({"ok": False, "error": "Request body must be a JSON object"})
    run_id = body.get("run_id")
    if not isinstance(run_id, str):
        return web.json_response({"ok": False, "error": "run_id must be a string"})
    note = body.get("note")
    if not isinstance(note, str):
        return web.json_response({"ok": False, "error": "note must be a string"})

    def _go():
        try:
            with _LOCK:
                return assets_core.set_run_note(_arch, run_id, note)
        except Exception:
            # 不回显异常文本(OSError 的 str() 里带绝对路径)
            return {"ok": False, "error": "Note failed"}

    result = await asyncio.to_thread(_go)
    return web.json_response(result)


@PromptServer.instance.routes.post("/asset/scan")
@_same_origin_only
async def asset_scan(request):
    # 强制刷新一次服务端提示词索引: 刚跑完的任务要能立刻按文件名找回 prompt
    _hist.refresh(force=True)

    def _go():
        try:
            with _LOCK:
                return assets_core.scan_all(_current_output_dir(), _arch, _state, _cfg, _prompt_resolver)
        except Exception:
            # 归档目录只读/占满/被同名文件挡住时返回结构化错误, 不要 500
            return -1

    n = await asyncio.to_thread(_go)
    if n < 0:
        return web.json_response({"ok": False, "error": "Scan failed"}, status=200)
    return web.json_response({"ok": True, "new": n})


@PromptServer.instance.routes.post("/asset/backup")
@_same_origin_only
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


# Make browser-native audio/video previews work consistently on Windows, where
# Python's mimetypes registry may not include common codecs and formats.
for _audio_ext, _audio_mime in {
    ".aac": "audio/aac",
    ".aif": "audio/aiff",
    ".aiff": "audio/aiff",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".oga": "audio/ogg",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".wav": "audio/wav",
    ".wma": "audio/x-ms-wma",
    ".webm": "video/webm",
}.items():
    mimetypes.add_type(_audio_mime, _audio_ext, strict=True)


@PromptServer.instance.routes.get("/asset/file")
async def asset_file(request):
    rel = request.rel_url.query.get("p", "")
    if not isinstance(rel, str):
        return web.Response(status=400, text="bad request")
    p = assets_core.safe_media_path(_arch, rel)
    if not p:
        return web.Response(status=404, text="not found")
    content_type = mimetypes.guess_type(p.name, strict=True)[0]
    headers = {"Content-Type": content_type} if content_type else None
    return web.FileResponse(p, headers=headers)


@PromptServer.instance.routes.get("/asset/workflow")
async def asset_workflow(request):
    rel = request.rel_url.query.get("p", "")
    if not isinstance(rel, str):
        return web.Response(status=400, text="bad request")
    p = assets_core.safe_media_path(_arch, rel, workflow_only=True)
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


def _browse_children(path):
    """只列出可安全展示的子目录。

    - 已位于允许根内部: 列出其所有普通子目录(跳过隐藏项与符号链接)。
    - 仅处于允许根的父级链上: 只列出"通往允许根"的那一级目录, 不泄露同级其它目录名。
    """
    p = os.path.abspath(path).lower()
    inside = any(p == r or p.startswith(r + os.sep) for r in _browsable_roots())
    names = []
    try:
        entries = os.scandir(path)
    except OSError:
        return names
    with entries:
        for entry in entries:
            try:
                if entry.name.startswith(".") or entry.is_symlink() or not entry.is_dir():
                    continue
            except OSError:
                continue
            child = os.path.abspath(entry.path).lower()
            if inside:
                names.append(entry.name)
            elif any(r == child or r.startswith(child + os.sep) for r in _browsable_roots()):
                names.append(entry.name)
    return sorted(names)


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
        dirs = _browse_children(path)
        return web.json_response({"ok": True, "path": path, "parent": parent, "dirs": dirs})
    except Exception:
        # 不回显异常文本: 目录枚举失败的 OSError 里带绝对路径
        return web.json_response({"ok": False, "error": "Cannot read directory"})
