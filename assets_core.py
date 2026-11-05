# -*- coding: utf-8 -*-
"""
ComfyUI 资产管理插件核心库
============================
无 ComfyUI 依赖, 可独立测试。提供: 配置读写 / 元数据提取 / 归档 / 扫描 /
索引列表 / 删除 / 备份 / 媒体文件安全读取。
"""

import hashlib
import json
import os
import shutil
import stat
import time
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image
    HAS_PIL = True
except Exception:
    HAS_PIL = False

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
VIDEO_EXT = {".mp4", ".webm", ".mov", ".mkv", ".gif"}
AUDIO_EXT = {".wav", ".mp3", ".flac", ".ogg", ".opus", ".m4a", ".aac", ".aiff", ".aif", ".wma"}
ALL_EXT = IMAGE_EXT | VIDEO_EXT | AUDIO_EXT
NEG_HINTS = ("negative", "neg prompt", "neg", "负")

# ---------------------------------------------------------------------------
# 安全说明(Security): 不启动任何外部进程
# ---------------------------------------------------------------------------
# 历史问题(见 Comfy Registry 审核 policy-v0.5 command-injection /
# policy-v0.2 ARBITRARY_FILE_LAUNCH):
# 旧版通过 ffprobe/ffmpeg 读取视频元数据与抽帧, 其可执行文件路径来自配置, 而配置又能被
# /asset/set_config 的请求体直接改写 -> 未认证请求可注入任意路径导致命令执行。
#
# 现策略(彻底移除攻击面): 视频元数据与缩略图改用 PyAV(av) 在**进程内**完成,
# 本文件不再 import subprocess, 不再解析/执行任何外部可执行文件, 不存在命令注入面。
# 相应地, 配置里也移除了 ffprobe/ffmpeg 两项。
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "output_dir": "",   # 空 = 使用 ComfyUI 默认 output
    "archive_dir": "",  # 空 = 使用 <ComfyUI>/asset_archive
    "backup_dir": "",   # 空 = 使用 <ComfyUI>/asset_backups
    "auto_archive": True,
    "archive_existing": False,  # 首次运行是否归档 output 里已有的历史产物(False=只归档安装后的新产物)
    "thumb_width": 480,
    "interval_sec": 10,
}

# /asset/set_config 允许客户端修改的键白名单(其余一律忽略并报错)
CLIENT_SETTABLE_KEYS = {
    "output_dir", "archive_dir", "backup_dir",
    "auto_archive", "archive_existing",
    "thumb_width", "interval_sec",
}

# 数值型配置的合法范围(下限, 上限)
NUMERIC_LIMITS = {
    "thumb_width": (16, 4096),
    "interval_sec": (1, 3600),
}


def load_config(base_dir):
    """读取配置。

    安全约束: 只接受已知键，并验证路径、布尔值和数值类型/范围；忽略未知或格式错误字段。
    配置里已不含任何可执行文件路径, 因此不存在"配置 -> 执行外部程序"的链路。
    """
    cfg = dict(DEFAULT_CONFIG)
    fp = Path(base_dir) / "config.json"
    if fp.is_file():
        try:
            user = json.loads(fp.read_text(encoding="utf-8"))
            if isinstance(user, dict):
                path_keys = {"output_dir", "archive_dir", "backup_dir"}
                boolean_keys = {"auto_archive", "archive_existing"}
                for k, v in user.items():
                    if k in path_keys and isinstance(v, str):
                        cfg[k] = v
                    elif k in boolean_keys and isinstance(v, bool):
                        cfg[k] = v
                    elif k in NUMERIC_LIMITS and isinstance(v, int) and not isinstance(v, bool):
                        lo, hi = NUMERIC_LIMITS[k]
                        if lo <= v <= hi:
                            cfg[k] = v
        except Exception:
            pass
    return cfg


def save_config(base_dir, cfg):
    fp = Path(base_dir) / "config.json"
    tmp = fp.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, fp)


def state_file(archive_dir):
    return Path(archive_dir) / "archive_state.json"


def load_state(archive_dir):
    try:
        return json.loads(state_file(archive_dir).read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(archive_dir, state):
    fp = state_file(archive_dir)
    tmp = Path(str(fp) + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, fp)


# ---------------------------------------------------------------------------
# 分类: 文件夹(自动派生) 与 我的分类(手动, 平铺一层)
# ---------------------------------------------------------------------------

CATEGORY_NAME_MAX = 40
CATEGORY_LIMIT = 200


def categories_file(archive_dir):
    return Path(archive_dir) / "categories.json"


def _clean_category_name(name):
    if not isinstance(name, str):
        return ""
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    return name[:CATEGORY_NAME_MAX]


def _normalize_parents(items):
    """把 parent 校正成"只能挂在一级分类下": 丢掉悬空/自指/成环的父引用。"""
    by_id = {c["id"]: c for c in items}
    for c in items:
        p = c.get("parent")
        if not isinstance(p, str) or p == c["id"] or p not in by_id:
            c["parent"] = None
    # 父分类自己也挂了父 → 链条压平, 保证最多两层
    for _ in range(len(items)):
        changed = False
        for c in items:
            p = c.get("parent")
            if p and by_id[p].get("parent"):
                c["parent"] = None
                changed = True
        if not changed:
            break
    return items


def load_categories(archive_dir):
    """读取分类清单, 对损坏/异常内容保持容错, 只返回结构合法的条目。"""
    try:
        raw = json.loads(categories_file(archive_dir).read_text(encoding="utf-8"))
    except Exception:
        return {"categories": []}
    items = raw.get("categories") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        return {"categories": []}
    seen, out = set(), []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        cid, name = item.get("id"), _clean_category_name(item.get("name"))
        if not isinstance(cid, str) or not cid or cid in seen or not name:
            continue
        seen.add(cid)
        order = item.get("order")
        parent = item.get("parent")
        out.append({
            "id": cid,
            "name": name,
            "order": order if isinstance(order, int) else idx,
            "parent": parent if isinstance(parent, str) and parent else None,
        })
    out = _normalize_parents(out)
    out.sort(key=lambda c: c["order"])
    return {"categories": out[:CATEGORY_LIMIT]}


def save_categories(archive_dir, data):
    fp = categories_file(archive_dir)
    tmp = Path(str(fp) + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, fp)


def _siblings(items, parent):
    """同一层级的分类(同名只在该层内算重名)。"""
    want = parent or None
    return [c for c in items if (c.get("parent") or None) == want]


def create_category(archive_dir, name, parent=None):
    name = _clean_category_name(name)
    if not name:
        return {"ok": False, "error": "Category name is required"}
    data = load_categories(archive_dir)
    items = data["categories"]
    if len(items) >= CATEGORY_LIMIT:
        return {"ok": False, "error": "Too many categories"}
    parent = parent or None
    if parent is not None:
        if not isinstance(parent, str) or not any(c["id"] == parent for c in items):
            return {"ok": False, "error": "Parent category not found"}
        if any(c["id"] == parent and c.get("parent") for c in items):
            return {"ok": False, "error": "Only one level of nesting is supported"}
    sibs = _siblings(items, parent)
    if any(c["name"].casefold() == name.casefold() for c in sibs):
        return {"ok": False, "error": "Category already exists"}
    cid = uuid.uuid4().hex[:8]
    item = {"id": cid, "name": name, "order": max([c["order"] for c in sibs], default=-1) + 1}
    if parent:
        item["parent"] = parent
    items.append(item)
    save_categories(archive_dir, data)
    return {"ok": True, "category": {"id": cid, "name": name, "parent": parent}, "categories": items}


def rename_category(archive_dir, category_id, name):
    name = _clean_category_name(name)
    if not name:
        return {"ok": False, "error": "Category name is required"}
    data = load_categories(archive_dir)
    for item in data["categories"]:
        if item["id"] == category_id:
            sib = item.get("parent") or None
            if any(c["id"] != category_id and (c.get("parent") or None) == sib
                   and c["name"].casefold() == name.casefold() for c in data["categories"]):
                return {"ok": False, "error": "Category already exists"}
            item["name"] = name
            save_categories(archive_dir, data)
            return {"ok": True, "categories": data["categories"]}
    return {"ok": False, "error": "Category not found"}


def delete_category(archive_dir, category_id):
    """删除分类: 该分类下的产物回到未分类, 子分类上提一层(不连带删除)。"""
    data = load_categories(archive_dir)
    target = next((c for c in data["categories"] if c["id"] == category_id), None)
    if target is None:
        return {"ok": False, "error": "Category not found"}
    data["categories"] = [c for c in data["categories"] if c["id"] != category_id]
    promoted = 0
    for c in data["categories"]:
        if c.get("parent") == category_id:
            if target.get("parent"):
                c["parent"] = target["parent"]
            else:
                c.pop("parent", None)
            promoted += 1
    save_categories(archive_dir, data)
    cleared = _clear_category_from_runs(archive_dir, category_id)
    return {"ok": True, "categories": data["categories"], "cleared": cleared, "promoted": promoted}


def _clear_category_from_runs(archive_dir, category_id):
    """把指定分类从所有归档记录上摘掉, 只改 info.json, 不动媒体文件。"""
    arch = Path(archive_dir).resolve()
    cleared = 0
    for info_file in arch.glob("*/*/info.json"):
        try:
            if info_file.is_symlink() or not info_file.is_file():
                continue
            info = json.loads(info_file.read_text(encoding="utf-8"))
            if not isinstance(info, dict) or info.get("category") != category_id:
                continue
            info["category"] = None
            tmp = info_file.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, info_file)
            cleared += 1
        except Exception:
            continue
    return cleared


def resolve_folder(info):
    """返回归档记录所属文件夹: 优先 info.folder, 缺失时由 source_rel 派生。"""
    folder = info.get("folder") if isinstance(info, dict) else None
    if isinstance(folder, str) and folder.strip() and folder.strip() != ".":
        return folder.strip().replace("\\", "/").strip("/")
    rel = info.get("source_rel") if isinstance(info, dict) else None
    if not isinstance(rel, str):
        return ""
    parent = str(Path(rel).parent).replace("\\", "/")
    return "" if parent in (".", "") else parent.strip("/")


def _run_dir_for(archive_dir, run_id):
    """校验 run_id 并返回归档目录内的任务目录, 不合法则返回 None。"""
    arch = Path(archive_dir).resolve()
    if not isinstance(run_id, str) or not run_id.strip():
        return None
    try:
        run_dir = (arch / run_id).resolve(strict=True)
        run_dir.relative_to(arch)
    except (OSError, RuntimeError, ValueError):
        return None
    if run_dir == arch or run_dir.is_symlink() or not run_dir.is_dir():
        return None
    return run_dir


def assign_category(archive_dir, run_ids, category_id):
    """把一组归档记录改到指定分类 (category_id=None 表示移出分类)。

    只改 info.json, 不动媒体文件、不移动归档目录, 因此毫秒级且可随时改回。
    """
    if not isinstance(run_ids, list):
        return {"ok": False, "error": "run_ids must be an array"}
    if len(run_ids) > 500:
        return {"ok": False, "error": "too many run_ids (max 500)"}
    if category_id is not None:
        known = {c["id"] for c in load_categories(archive_dir)["categories"]}
        if category_id not in known:
            return {"ok": False, "error": "Category not found"}
    updated, skipped = [], []
    for run_id in run_ids:
        run_dir = _run_dir_for(archive_dir, run_id)
        if not run_dir:
            skipped.append({"run": run_id, "reason": "invalid path"})
            continue
        info_file = run_dir / "info.json"
        if info_file.is_symlink() or not info_file.is_file():
            skipped.append({"run": run_id, "reason": "missing info.json"})
            continue
        try:
            info = json.loads(info_file.read_text(encoding="utf-8"))
        except Exception:
            skipped.append({"run": run_id, "reason": "unreadable info.json"})
            continue
        if not isinstance(info, dict):
            skipped.append({"run": run_id, "reason": "invalid info.json"})
            continue
        info["category"] = category_id
        tmp = info_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, info_file)
        updated.append(run_id)
    return {"ok": True, "updated": updated, "skipped": skipped}


def path_is_within(path, root):
    """Return whether the resolved path is equal to or below root."""
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except (OSError, RuntimeError, TypeError, ValueError):
        return False


def paths_overlap(path_a, path_b):
    """Return True when either resolved directory contains the other."""
    return path_is_within(path_a, path_b) or path_is_within(path_b, path_a)


def ensure_dir(path, *fallbacks):
    """Return the first usable directory, creating it when needed.

    路径完全由运行时决定: 配置里的路径可能来自另一台机器(盘符不存在)或已被移动,
    这里逐个尝试并在失败时回退到调用方给出的默认目录, 避免插件因一个坏路径而无法加载。
    """
    for candidate in (path,) + fallbacks:
        if not candidate:
            continue
        try:
            p = Path(candidate).expanduser()
            p.mkdir(parents=True, exist_ok=True)
            if p.is_dir():
                return str(p)
        except (OSError, ValueError):
            continue
    return ""


# ---------------------------------------------------------------------------
# 元数据提取
# ---------------------------------------------------------------------------

def safe_json(s):
    if isinstance(s, (dict, list)):
        return s
    if not isinstance(s, str):
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def _exif_user_comment(exif_bytes):
    try:
        import piexif
        exif_dict = piexif.load(exif_bytes)
        uc = exif_dict.get("Exif", {}).get(piexif.ExifIFD.UserComment)
        if not uc:
            return None
        if isinstance(uc, bytes):
            for enc in ("utf-8", "utf-16"):
                try:
                    s = uc.decode(enc).strip("\x00")
                    if s:
                        return s
                except Exception:
                    pass
        return None
    except Exception:
        return None


def extract_image_metadata(path):
    prompt = workflow = None
    try:
        with Image.open(path) as im:
            info = dict(im.info)
    except Exception:
        info = {}
    prompt = info.get("prompt")
    workflow = info.get("workflow")
    if not (prompt or workflow) and info.get("exif"):
        uc = _exif_user_comment(info["exif"])
        if uc:
            obj = safe_json(uc)
            if isinstance(obj, dict):
                prompt = prompt or obj.get("prompt") or obj.get("prompt_info")
                workflow = workflow or obj.get("workflow")
    return prompt, workflow


def extract_video_metadata(path, cfg):
    """读取视频容器标签里的 prompt/workflow。

    实现说明(安全): 使用 PyAV(PyAV/av) 在进程内解析容器元数据, **不启动任何外部进程**,
    因此既无命令注入面, 也不需要 ffprobe。ComfyUI 运行环境自带 av(以及 ffmpeg 运行库)。
    读取不到(未安装 av / 无标签)时返回 (None, None), 由上层回落到执行记录兜底。
    """
    try:
        import av
    except Exception:
        return None, None
    try:
        with av.open(str(path)) as container:
            md = dict(container.metadata or {})
    except Exception:
        return None, None
    prompt = md.get("prompt")
    workflow = md.get("workflow")
    return prompt, workflow


def extract_audio_metadata(path):
    """读取音频容器元数据与时长, 不启动外部进程。

    PyAV 为可选依赖: 不可用或格式不支持时仍会归档并可在浏览器中播放文件;
    提示词和工作流可由 ComfyUI 执行历史兜底找回。
    """
    try:
        import av
    except Exception:
        return None, None, None
    try:
        with av.open(str(path)) as container:
            md = dict(container.metadata or {})
            duration = None
            if container.duration is not None:
                duration = float(container.duration) / float(av.time_base)
            elif container.streams.audio:
                stream = container.streams.audio[0]
                if stream.duration is not None and stream.time_base is not None:
                    duration = float(stream.duration * stream.time_base)
    except Exception:
        return None, None, None
    return md.get("prompt"), md.get("workflow"), duration


def parse_prompt_graph(graph):
    texts, params, models, seeds = [], {}, {}, []
    if not isinstance(graph, dict):
        return {"positive": "", "negative": "", "texts": texts, "params": params, "models": []}
    for nid, node in graph.items():
        if not isinstance(node, dict):
            continue
        cls = node.get("class_type") or ""
        meta = node.get("_meta")
        meta = meta if isinstance(meta, dict) else {}
        title = meta.get("title") or cls
        inputs = node.get("inputs") or {}
        if not isinstance(inputs, dict):
            continue
        title_l = str(title).lower()
        for k, v in inputs.items():
            if not isinstance(v, str) or not v.strip():
                continue
            kk = k.lower()
            looks_path = any(x in v for x in (".safetensors", ".ckpt", ".gguf", ".sft", ".onnx", ".pth", ".pt", ".bin"))
            looks_text = (kk in ("text", "prompt", "value", "positive", "negative",
                                 "caption", "lyrics", "style", "abc", "song_prompt",
                                 "conditioned_prompt", "integrated_multimodal_description")
                          or ("text" in kk or "prompt" in kk))
            if looks_text and not looks_path and len(v) < 100000:
                is_neg = (kk == "negative" or any(h in title_l for h in NEG_HINTS) or "负" in title)
                texts.append({"node": str(nid), "title": title,
                              "role": "negative" if is_neg else "positive", "text": v})
            if looks_path:
                models.setdefault(cls or title, []).append(v)
        for k, v in inputs.items():
            kk = k.lower()
            if isinstance(v, (int, float)) or (isinstance(v, str) and v.strip()):
                if kk in ("seed", "noise_seed"):
                    try:
                        seeds.append(int(v))
                    except Exception:
                        pass
                elif kk in ("steps", "video_steps", "audio_steps", "cfg", "cfg_scale",
                            "shift", "shift_video", "shift_audio", "sampler_name", "scheduler",
                            "width", "height", "frame_rate", "length", "denoise",
                            "strength_model", "aspect_ratio", "megapixels", "multiple",
                            "quality", "crf", "start_step", "end_step"):
                    if kk not in params:
                        params[kk] = v
    positive = "\n".join(t["text"] for t in texts if t["role"] == "positive")
    negative = "\n".join(t["text"] for t in texts if t["role"] == "negative")
    if seeds:
        params["seeds"] = seeds
    model_list, seen = [], set()
    for names in models.values():
        for n in names:
            if n not in seen:
                seen.add(n)
                model_list.append(n)
    return {"positive": positive, "negative": negative, "texts": texts,
            "params": params, "models": model_list}


# ---------------------------------------------------------------------------
# 归档
# ---------------------------------------------------------------------------

def make_video_thumb(src, dst, cfg):
    """抽视频首帧作为缩略图。

    实现说明(安全): 使用 PyAV 在进程内解码抽帧并交给 PIL 缩放保存, **不启动任何外部进程**,
    因此无命令注入面, 也不需要 ffmpeg 可执行文件。
    读取不到(未安装 av / 解码失败)时返回 None(前端会显示占位图)。
    """
    try:
        import av
    except Exception:
        return None
    try:
        width = int(cfg.get("thumb_width", 480))
    except Exception:
        width = 480
    width = max(16, min(width, 4096))
    try:
        with av.open(str(src)) as container:
            if not container.streams.video:
                return None
            stream = container.streams.video[0]
            frame = None
            for f in container.decode(stream):
                frame = f
                break
            if frame is None:
                return None
            img = frame.to_image()
        if HAS_PIL:
            img = img.convert("RGB")
        img.thumbnail((width, width))
        img.save(str(dst), "JPEG", quality=82, optimize=True)
        if Path(dst).exists() and Path(dst).stat().st_size > 0:
            return "thumb.jpg"
    except Exception:
        pass
    if Path(dst).exists():
        try:
            Path(dst).unlink()
        except Exception:
            pass
    return None


CONTENT_HASH_LIMIT = 64 * 1024 * 1024   # 超过这个大小的文件不做内容去重(避免每次归档都读一遍大视频)


def file_content_hash(path, limit=CONTENT_HASH_LIMIT):
    """文件内容指纹。太大或读不了时返回 None(退化成只按路径去重)。"""
    try:
        if os.path.getsize(path) > limit:
            return None
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _content_index(state):
    """可写的 内容哈希 → 归档目录 索引(按需创建)。"""
    idx = state.get("__content__")
    if not isinstance(idx, dict):
        idx = {}
        state["__content__"] = idx
    return idx


def _content_lookup(state, content_hash):
    """只读查索引。命中不了就返回 None, 不往 state 里塞空壳。"""
    idx = state.get("__content__")
    if not isinstance(idx, dict) or not content_hash:
        return None
    hit = idx.get(content_hash)
    return hit if isinstance(hit, str) and hit else None


def _merge_moved_file(arch, prev_rel, rel, src, st, state, source_root):
    """同一份内容换了路径(移动/改名): 更新原记录而不是再归档一份。

    只有"旧路径上的文件已经不在了"才合并; 两份都还在说明用户是真的存了两份, 保持独立。
    """
    if not isinstance(prev_rel, str) or not prev_rel:
        return None
    run_dir = Path(arch) / prev_rel
    info_file = run_dir / "info.json"
    if not info_file.is_file():
        return None
    try:
        info = json.loads(info_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(info, dict):
        return None
    old_rel = info.get("source_rel")
    if isinstance(old_rel, str) and old_rel and source_root is not None:
        try:
            old_src = Path(source_root) / old_rel
            if old_src.is_file() and not old_src.is_symlink():
                return None      # 旧文件还在 → 真的是两份, 不合并
        except OSError:
            pass
    info["source_rel"] = rel
    info["folder"] = resolve_folder({"source_rel": rel})
    info["file_size"] = st.st_size
    info["generated_at"] = datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")
    info["moved_at"] = datetime.now().isoformat(timespec="seconds")
    tmp = info_file.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, info_file)
    except OSError:
        return None
    if isinstance(old_rel, str) and old_rel and old_rel != rel:
        state.pop(old_rel, None)
    state[rel] = {"size": st.st_size, "mtime_ns": st.st_mtime_ns}
    return {"merged": True, "dir": prev_rel, "source_rel": rel}


def archive_file(rel, src, archive_dir, state, cfg, prompt_resolver=None, source_root=None):
    src = Path(src)
    try:
        st = src.lstat()
        if not stat.S_ISREG(st.st_mode) or src.is_symlink():
            return None
        resolved_src = src.resolve(strict=True)
        if source_root is not None and not path_is_within(resolved_src, source_root):
            return None
        src = resolved_src
        st = src.stat()
    except (OSError, RuntimeError):
        return None
    state_key = {"size": st.st_size, "mtime_ns": st.st_mtime_ns}
    if state.get(rel) == state_key:
        return None
    ext = Path(rel).suffix.lower()
    if ext in IMAGE_EXT:
        kind = "image"
    elif ext in VIDEO_EXT:
        kind = "video"
    elif ext in AUDIO_EXT:
        kind = "audio"
    else:
        return None
    arch = Path(archive_dir)
    media_duration = None

    # 内容没变、只是路径变了(用户在资源管理器里挪动/改名) → 复用已有记录
    content_hash = file_content_hash(src)
    if content_hash:
        merged = _merge_moved_file(arch, _content_lookup(state, content_hash),
                                   rel, src, st, state, source_root)
        if merged:
            return merged

    if kind == "image":
        prompt_raw, workflow_raw = extract_image_metadata(src)
    elif kind == "video":
        prompt_raw, workflow_raw = extract_video_metadata(src, cfg)
    else:
        prompt_raw, workflow_raw, media_duration = extract_audio_metadata(src)

    # 文件里没有元数据时, 从 ComfyUI 服务端执行历史按文件名找回
    # (覆盖: 外部拖进来的图 / --disable-metadata / 不写元数据的保存节点)
    prompt_source = "file"
    if not prompt_raw and prompt_resolver is not None:
        try:
            hit = prompt_resolver(rel, src)
        except Exception:
            hit = None
        if hit:
            try:
                hist_prompt, hist_workflow = hit
                if isinstance(hist_prompt, dict) and hist_prompt:
                    prompt_raw = json.dumps(hist_prompt, ensure_ascii=False)
                    prompt_source = "history"
                if workflow_raw is None and isinstance(hist_workflow, dict) and hist_workflow:
                    workflow_raw = json.dumps(hist_workflow, ensure_ascii=False)
            except Exception:
                pass

    prompt_graph = safe_json(prompt_raw)
    workflow_graph = safe_json(workflow_raw)
    parsed = parse_prompt_graph(prompt_graph) if prompt_graph else \
        {"positive": "", "negative": "", "texts": [], "params": {}, "models": []}

    # 没有提示词的原因分类(给面板显示针对性说明用)
    if prompt_graph is None:
        no_prompt_reason = "no_embedded_metadata"
    elif not (parsed.get("texts") or []):
        no_prompt_reason = "no_text_nodes"
    else:
        no_prompt_reason = ""

    stem = Path(rel).stem
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in stem)[:60].strip("._")
    mtime = datetime.fromtimestamp(st.st_mtime)
    date_folder = mtime.strftime("%Y-%m-%d")
    run_id = mtime.strftime("%Y%m%d-%H%M%S") + "_" + (safe or "output")
    run_dir = arch / date_folder / run_id
    n = 2
    while run_dir.exists():
        run_dir = arch / date_folder / f"{run_id}_{n}"
        n += 1
    run_dir.mkdir(parents=True, exist_ok=True)

    media_name = Path(rel).name
    shutil.copy2(src, run_dir / media_name)

    thumb = None
    if kind == "image" and HAS_PIL:
        try:
            with Image.open(src) as im:
                im = im.convert("RGB")
                im.thumbnail((cfg["thumb_width"], cfg["thumb_width"]))
                im.save(run_dir / "thumb.jpg", "JPEG", quality=82, optimize=True)
                thumb = "thumb.jpg"
        except Exception:
            pass
    elif kind == "video":
        thumb = make_video_thumb(src, run_dir / "thumb.jpg", cfg)

    info = {
        "run_id": run_dir.name,
        "archived_at": datetime.now().isoformat(timespec="seconds"),
        "generated_at": mtime.isoformat(timespec="seconds"),
        "source_rel": rel,
        "folder": resolve_folder({"source_rel": rel}),
        "category": None,
        "media": media_name,
        "kind": kind,
        "file_size": st.st_size,
        "media_duration": media_duration,
        "positive": parsed["positive"],
        "negative": parsed["negative"],
        "prompt_nodes": parsed["texts"],
        "params": parsed["params"],
        "models": parsed["models"],
        "has_workflow": workflow_graph is not None,
        "thumb": thumb,
        "prompt_json": prompt_graph,
        "workflow_json": workflow_graph,
        "prompt_source": prompt_source,
        "no_prompt_reason": no_prompt_reason,
    }
    if content_hash:
        info["content_hash"] = content_hash
    (run_dir / "info.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    if content_hash:
        _content_index(state)[content_hash] = run_dir.relative_to(arch).as_posix()

    lines = ["=== ComfyUI 产物信息 ===",
             f"来源: {rel}", f"生成时间: {info['generated_at']}",
             f"类型: { {'image': '图片', 'video': '视频', 'audio': '音频'}[kind] }",
             f"大小: {st.st_size / 1024:.0f} KB"]
    if parsed["models"]:
        lines.append("模型/LoRA: " + ", ".join(parsed["models"]))
    if parsed["params"]:
        lines.append("参数: " + json.dumps(parsed["params"], ensure_ascii=False))
    lines += ["", "=== 正向提示词 ===", parsed["positive"] or "(未检测到)"]
    if parsed["negative"]:
        lines += ["", "=== 负向提示词 ===", parsed["negative"]]
    (run_dir / "prompt.txt").write_text("\n".join(lines), encoding="utf-8")

    if workflow_graph:
        (run_dir / "workflow.json").write_text(
            json.dumps(workflow_graph, ensure_ascii=False, indent=1), encoding="utf-8")

    state[rel] = state_key
    return {"run": run_dir.name, "dir": run_dir.relative_to(arch).as_posix(), "kind": kind}


def scan_all(output_dir, archive_dir, state, cfg, prompt_resolver=None):
    out = Path(output_dir).resolve()
    arch = Path(archive_dir).resolve()
    if not out.is_dir() or paths_overlap(out, arch):
        return 0
    new_runs = []
    state_changed = False
    archive_existing = bool(cfg.get("archive_existing", False))
    baseline_done = bool(state.get("__baseline_done__", False))
    for root, dirs, files in os.walk(out, followlinks=False):
        root_path = Path(root)
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".")
            and not (root_path / d).is_symlink()
            and path_is_within(root_path / d, out)
        ]
        for fn in files:
            if fn.startswith("."):
                continue
            if Path(fn).suffix.lower() not in ALL_EXT:
                continue
            src = root_path / fn
            rel = src.relative_to(out).as_posix()
            try:
                st = src.lstat()
                if not stat.S_ISREG(st.st_mode) or src.is_symlink():
                    continue
                if not path_is_within(src.resolve(strict=True), out):
                    continue
            except (OSError, RuntimeError):
                continue
            cur_key = {"size": st.st_size, "mtime_ns": st.st_mtime_ns}
            if state.get(rel) == cur_key:
                continue
            # 等待写入完成
            last = None
            t0 = time.time()
            stable = False
            while time.time() - t0 < 6.0:
                try:
                    cur = (os.stat(src).st_size, os.stat(src).st_mtime_ns)
                except OSError:
                    break
                if cur == last:
                    stable = True
                    break
                last = cur
                time.sleep(0.5)
            if not stable:
                continue
            if rel in state:
                # 已记录过(归档过或基线过), 文件有变化 → 归档新版本
                r = archive_file(rel, src, archive_dir, state, cfg, prompt_resolver, source_root=out)
                if r and r.get("merged"):
                    state_changed = True
                elif r:
                    new_runs.append(r)
            elif baseline_done or archive_existing:
                # 基线已建立后的新文件, 或用户开启"归档历史" → 归档
                r = archive_file(rel, src, archive_dir, state, cfg, prompt_resolver, source_root=out)
                if r and r.get("merged"):
                    state_changed = True
                elif r:
                    new_runs.append(r)
            else:
                # 首次扫描且不归档历史: 只记录基线(不复制文件)
                state[rel] = cur_key
                state_changed = True
    if not baseline_done:
        state["__baseline_done__"] = True
        state_changed = True
    if new_runs or state_changed:
        save_state(archive_dir, state)
    return len(new_runs)


# ---------------------------------------------------------------------------
# 索引 / 列表
# ---------------------------------------------------------------------------

def list_runs(archive_dir):
    arch = Path(archive_dir).resolve()
    runs = []
    if not arch.is_dir():
        return runs
    for date_dir in arch.iterdir():
        if date_dir.is_symlink() or not date_dir.is_dir() or not path_is_within(date_dir, arch):
            continue
        for run_dir in date_dir.iterdir():
            if run_dir.is_symlink() or not run_dir.is_dir() or not path_is_within(run_dir, arch):
                continue
            info_file = run_dir / "info.json"
            if info_file.is_symlink() or not info_file.is_file() or not path_is_within(info_file, arch):
                continue
            try:
                info = json.loads(info_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(info, dict):
                continue
            generated_at = info.get("generated_at")
            media = info.get("media")
            if not isinstance(generated_at, str) or not isinstance(media, str):
                continue
            if (Path(media).name != media or media in (".", "..")
                    or "/" in media or chr(92) in media):
                continue
            kind = info.get("kind")
            if kind not in ("image", "video", "audio"):
                kind = "image"
            thumb = info.get("thumb")
            if not isinstance(thumb, str) or Path(thumb).name != thumb:
                thumb = None
            models = info.get("models")
            if not isinstance(models, list):
                models = []
            models = [model for model in models if isinstance(model, str)]
            params = info.get("params")
            if not isinstance(params, dict):
                params = {}
            runs.append({
                "id": run_dir.name,
                "date": generated_at[:10],
                "time": generated_at,
                "name": info.get("source_rel") if isinstance(info.get("source_rel"), str) else run_dir.name,
                "kind": kind,
                "folder": resolve_folder(info),
                "category": info.get("category") if isinstance(info.get("category"), str) else None,
                "media": media,
                "media_duration": info.get("media_duration") if isinstance(info.get("media_duration"), (int, float)) else None,
                "thumb": thumb,
                "dir": run_dir.relative_to(arch).as_posix(),
                "positive": info.get("positive") if isinstance(info.get("positive"), str) else "",
                "negative": info.get("negative") if isinstance(info.get("negative"), str) else "",
                "models": models,
                "params": params,
                "has_workflow": bool(info.get("has_workflow")),
                "prompt_source": info.get("prompt_source") if isinstance(info.get("prompt_source"), str) else "file",
                "no_prompt_reason": info.get("no_prompt_reason") if isinstance(info.get("no_prompt_reason"), str) else "",
            })
    runs.sort(key=lambda r: r.get("time") or "", reverse=True)
    return runs


# ---------------------------------------------------------------------------
# 删除
# ---------------------------------------------------------------------------

def delete_run(archive_dir, output_dir, state, run_id):
    arch = Path(archive_dir).resolve()
    out = Path(output_dir).resolve() if output_dir else None
    if not run_id or not isinstance(run_id, str):
        return {"ok": False, "error": "Missing run_id"}
    run_dir = (arch / run_id).resolve()
    if run_dir == arch or not path_is_within(run_dir, arch):
        return {"ok": False, "error": "Invalid archive path"}
    info_file = run_dir / "info.json"
    if not (run_dir.is_dir() and info_file.is_file()):
        return {"ok": False, "error": "Archive entry not found"}
    source_rel = None
    try:
        info = json.loads(info_file.read_text(encoding="utf-8"))
        if isinstance(info, dict) and isinstance(info.get("source_rel"), str):
            source_rel = info["source_rel"]
    except Exception:
        pass
    shutil.rmtree(run_dir)
    # 记录没了, 内容索引里指向它的条目也一起清掉(否则以后同内容会被指向空目录)
    rel_dir = run_dir.relative_to(arch).as_posix()
    idx = state.get("__content__")
    if isinstance(idx, dict):
        for h in [k for k, v in idx.items() if v == rel_dir]:
            idx.pop(h, None)
    if source_rel and out:
        src = out / source_rel
        # Never follow a source symlink during deletion, and keep the resolved target under output.
        if not src.is_symlink() and src.is_file() and path_is_within(src, out):
            try:
                src.unlink()
            except Exception:
                pass
        state.pop(source_rel, None)
    save_state(archive_dir, state)
    return {"ok": True, "source_rel": source_rel}


# ---------------------------------------------------------------------------
# 备份
# ---------------------------------------------------------------------------

def default_asset_dirs(base_dir):
    """通用默认目录(相对 ComfyUI 安装目录, 与机器无关)"""
    comfy_dir = Path(base_dir).resolve().parent.parent
    return str(comfy_dir / "asset_archive"), str(comfy_dir / "asset_backups")


def backup_assets(cfg, base_dir, workflow_dirs=None):
    _arch_default, _bak_default = default_asset_dirs(base_dir)
    archive_dir = Path(cfg.get("archive_dir") or _arch_default).resolve()
    configured_backup = Path(cfg.get("backup_dir") or _bak_default).resolve()
    workflow_dirs = [Path(p).resolve() for p in (workflow_dirs or []) if p]
    source_roots = [archive_dir] + workflow_dirs
    if any(paths_overlap(configured_backup, root) for root in source_roots):
        return {"ok": False, "error": "Backup directory must not overlap a backup source"}

    # 配置的备份目录可能位于已移除的盘符/只读位置: 回退到默认目录, 不让备份直接失败
    usable_backup = ensure_dir(str(configured_backup), _bak_default)
    if not usable_backup:
        return {"ok": False, "error": "No writable backup directory available"}
    backup_dir = Path(usable_backup)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    unique = uuid.uuid4().hex[:8]
    zip_name = f"ComfyUI_asset_backup_{stamp}_{unique}.zip"
    zip_path = backup_dir / zip_name
    temp_path = backup_dir / f".{zip_name}.tmp"

    def _add(zf, root, arcname):
        root = Path(root).resolve()
        if not root.exists() or not root.is_dir():
            return 0
        n = 0
        for f in root.rglob("*"):
            try:
                if f.is_symlink():
                    continue
                resolved = f.resolve(strict=True)
                if not path_is_within(resolved, root) or not resolved.is_file():
                    continue
                rel = f.relative_to(root).as_posix()
                zf.write(resolved, f"{arcname}/{rel}")
                n += 1
            except (OSError, RuntimeError, ValueError):
                continue
        return n

    total = 0
    try:
        with zipfile.ZipFile(temp_path, "x", zipfile.ZIP_DEFLATED) as zf:
            total += _add(zf, archive_dir, "assets")
            for i, wd in enumerate(workflow_dirs):
                total += _add(zf, wd, f"workflows_{i}")
            cfg_file = Path(base_dir).resolve() / "config.json"
            if cfg_file.is_file() and not cfg_file.is_symlink() and path_is_within(cfg_file, base_dir):
                zf.write(cfg_file, "config.json")
                total += 1
        os.replace(temp_path, zip_path)
    except Exception:
        try:
            temp_path.unlink()
        except OSError:
            pass
        raise

    size = zip_path.stat().st_size
    return {"ok": True, "file": str(zip_path), "name": zip_path.name,
            "size": size, "files": total}


# ---------------------------------------------------------------------------
# 媒体文件安全读取
# ---------------------------------------------------------------------------

def safe_media_path(archive_dir, rel, workflow_only=False):
    """Return only manifest-listed files from an archive run."""
    arch = Path(archive_dir).resolve()
    try:
        p = (arch / rel).resolve(strict=True)
        parts = p.relative_to(arch).parts
    except (OSError, RuntimeError, ValueError, TypeError):
        return None
    if len(parts) != 3 or not p.is_file():
        return None

    date_dir = arch / parts[0]
    run_dir = date_dir / parts[1]
    info_file = run_dir / "info.json"
    if (date_dir.is_symlink() or run_dir.is_symlink() or info_file.is_symlink()
            or not info_file.is_file() or not path_is_within(info_file, arch)):
        return None
    try:
        info = json.loads(info_file.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(info, dict):
        return None

    if workflow_only:
        allowed = {"workflow.json"} if info.get("has_workflow") is True else set()
    else:
        allowed = set()
        for key in ("media", "thumb"):
            name = info.get(key)
            if (isinstance(name, str) and name not in (".", "..")
                    and "/" not in name and chr(92) not in name):
                allowed.add(name)
        if info.get("has_workflow") is True:
            allowed.add("workflow.json")
    if parts[2] not in allowed:
        return None
    return p
