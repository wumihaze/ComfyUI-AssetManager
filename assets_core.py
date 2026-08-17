# -*- coding: utf-8 -*-
"""
ComfyUI 资产管理插件核心库
============================
无 ComfyUI 依赖, 可独立测试。提供: 配置读写 / 元数据提取 / 归档 / 扫描 /
索引列表 / 删除 / 备份 / 媒体文件安全读取。
"""

import json
import os
import shutil
import subprocess
import time
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
ALL_EXT = IMAGE_EXT | VIDEO_EXT
NEG_HINTS = ("negative", "neg prompt", "neg", "负")

DEFAULT_CONFIG = {
    "output_dir": "",   # 空 = 使用 ComfyUI 默认 output
    "archive_dir": "",  # 空 = 使用 <ComfyUI>/asset_archive
    "backup_dir": "",   # 空 = 使用 <ComfyUI>/asset_backups
    "auto_archive": True,
    "thumb_width": 480,
    "interval_sec": 10,
    "ffprobe": "",      # 空 = 自动探测(优先 PATH 里的 ffprobe)
    "ffmpeg": "",       # 空 = 自动探测(优先 PATH 里的 ffmpeg)
}


def resolve_exe(fp):
    """解析可执行文件路径: 支持绝对路径 / 命令名(走 PATH) / 空(自动探测)"""
    if not fp:
        return None
    if os.path.isfile(fp):
        return fp
    import shutil
    return shutil.which(fp) or None


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

def load_config(base_dir):
    cfg = dict(DEFAULT_CONFIG)
    fp = Path(base_dir) / "config.json"
    if fp.is_file():
        try:
            user = json.loads(fp.read_text(encoding="utf-8"))
            if isinstance(user, dict):
                cfg.update(user)
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
    fp = resolve_exe(cfg.get("ffprobe"))
    if not fp:
        return None, None
    try:
        r = subprocess.run(
            [fp, "-v", "error", "-show_entries", "format_tags", "-of", "json", str(path)],
            capture_output=True, timeout=30,
        )
        data = json.loads(r.stdout.decode("utf-8", errors="replace") or "{}")
    except Exception:
        return None, None
    tags = (data.get("format") or {}).get("tags") or {}
    return tags.get("prompt"), tags.get("workflow")


def parse_prompt_graph(graph):
    texts, params, models, seeds = [], {}, {}, []
    if not isinstance(graph, dict):
        return {"positive": "", "negative": "", "texts": texts, "params": params, "models": []}
    for nid, node in graph.items():
        if not isinstance(node, dict):
            continue
        cls = node.get("class_type") or ""
        meta = node.get("_meta") or {}
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
    ff = resolve_exe(cfg.get("ffmpeg"))
    if not ff:
        return None
    width = int(cfg.get("thumb_width", 480))
    for ss in ("0", "1"):
        try:
            r = subprocess.run(
                [ff, "-y", "-hide_banner", "-loglevel", "error",
                 "-ss", ss, "-i", str(src), "-frames:v", "1",
                 "-vf", f"scale={width}:-2", str(dst)],
                capture_output=True, timeout=60,
            )
            if r.returncode == 0 and dst.exists() and dst.stat().st_size > 0:
                return "thumb.jpg"
        except Exception:
            pass
        if dst.exists():
            try:
                dst.unlink()
            except Exception:
                pass
    return None


def archive_file(rel, src, archive_dir, state, cfg):
    st = os.stat(src)
    state_key = {"size": st.st_size, "mtime_ns": st.st_mtime_ns}
    if state.get(rel) == state_key:
        return None
    ext = Path(rel).suffix.lower()
    kind = "video" if ext in VIDEO_EXT else "image"
    arch = Path(archive_dir)

    if kind == "image":
        prompt_raw, workflow_raw = extract_image_metadata(src)
    else:
        prompt_raw, workflow_raw = extract_video_metadata(src, cfg)
    prompt_graph = safe_json(prompt_raw)
    workflow_graph = safe_json(workflow_raw)
    parsed = parse_prompt_graph(prompt_graph) if prompt_graph else \
        {"positive": "", "negative": "", "texts": [], "params": {}, "models": []}

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
        "media": media_name,
        "kind": kind,
        "file_size": st.st_size,
        "positive": parsed["positive"],
        "negative": parsed["negative"],
        "prompt_nodes": parsed["texts"],
        "params": parsed["params"],
        "models": parsed["models"],
        "has_workflow": workflow_graph is not None,
        "thumb": thumb,
        "prompt_json": prompt_graph,
        "workflow_json": workflow_graph,
    }
    (run_dir / "info.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["=== ComfyUI 产物信息 ===",
             f"来源: {rel}", f"生成时间: {info['generated_at']}",
             f"类型: {'视频' if kind == 'video' else '图片'}",
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


def scan_all(output_dir, archive_dir, state, cfg):
    out = Path(output_dir)
    if not out.is_dir():
        return 0
    new_runs = []
    for root, dirs, files in os.walk(out):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fn in files:
            if fn.startswith("."):
                continue
            if Path(fn).suffix.lower() not in ALL_EXT:
                continue
            src = Path(root) / fn
            rel = src.relative_to(out).as_posix()
            try:
                st = os.stat(src)
            except OSError:
                continue
            if state.get(rel) == {"size": st.st_size, "mtime_ns": st.st_mtime_ns}:
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
            r = archive_file(rel, src, archive_dir, state, cfg)
            if r:
                new_runs.append(r)
    if new_runs:
        save_state(archive_dir, state)
    return len(new_runs)


# ---------------------------------------------------------------------------
# 索引 / 列表
# ---------------------------------------------------------------------------

def list_runs(archive_dir):
    arch = Path(archive_dir)
    runs = []
    if not arch.is_dir():
        return runs
    for date_dir in arch.iterdir():
        if not date_dir.is_dir():
            continue
        for run_dir in date_dir.iterdir():
            info_file = run_dir / "info.json"
            if not info_file.is_file():
                continue
            try:
                info = json.loads(info_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            runs.append({
                "id": info.get("run_id") or run_dir.name,
                "date": (info.get("generated_at") or "")[:10],
                "time": info.get("generated_at") or "",
                "name": info.get("source_rel") or run_dir.name,
                "kind": info.get("kind") or "image",
                "media": info.get("media"),
                "thumb": info.get("thumb"),
                "dir": run_dir.relative_to(arch).as_posix(),
                "positive": info.get("positive") or "",
                "negative": info.get("negative") or "",
                "models": info.get("models") or [],
                "params": info.get("params") or {},
                "has_workflow": bool(info.get("has_workflow")),
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
    if run_dir == arch or not str(run_dir).startswith(str(arch) + os.sep):
        return {"ok": False, "error": "Invalid archive path"}
    info_file = run_dir / "info.json"
    if not (run_dir.is_dir() and info_file.is_file()):
        return {"ok": False, "error": "Archive entry not found"}
    source_rel = None
    try:
        info = json.loads(info_file.read_text(encoding="utf-8"))
        source_rel = info.get("source_rel")
    except Exception:
        pass
    shutil.rmtree(run_dir)
    if source_rel and out:
        src = (out / source_rel).resolve()
        # 防穿越: source_rel 必须解析后仍位于 output 目录内
        if str(src).startswith(str(out) + os.sep) and src.is_file():
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
    archive_dir = Path(cfg.get("archive_dir") or _arch_default)
    backup_dir = Path(cfg.get("backup_dir") or _bak_default)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = backup_dir / f"ComfyUI_asset_backup_{stamp}.zip"
    workflow_dirs = workflow_dirs or []

    def _add(zf, root, arcname):
        root = Path(root)
        if not root.exists():
            return 0
        n = 0
        for f in root.rglob("*"):
            if f.is_file():
                rel = f.relative_to(root).as_posix()
                zf.write(f, f"{arcname}/{rel}")
                n += 1
        return n

    total = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        total += _add(zf, archive_dir, "assets")
        for i, wd in enumerate(workflow_dirs):
            if wd:
                total += _add(zf, wd, f"workflows_{i}")
        cfg_file = Path(base_dir) / "config.json"
        if cfg_file.is_file():
            zf.write(cfg_file, "config.json")
            total += 1
    size = zip_path.stat().st_size
    return {"ok": True, "file": str(zip_path), "name": zip_path.name,
            "size": size, "files": total}


# ---------------------------------------------------------------------------
# 媒体文件安全读取
# ---------------------------------------------------------------------------

def safe_media_path(archive_dir, rel):
    """校验 rel 在 archive_dir 内且为文件, 返回 Path 或 None"""
    arch = Path(archive_dir).resolve()
    p = (arch / rel).resolve()
    if not str(p).startswith(str(arch) + os.sep):
        return None
    if not p.is_file():
        return None
    return p
