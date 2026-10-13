# -*- coding: utf-8 -*-
"""
ComfyUI 服务端提示词索引(元数据兜底来源)
=========================================
插件一直靠读取**文件内嵌元数据**取提示词(PNG tEXt / WebP EXIF / MP4 ffmpeg tag)。
但下面这些情况文件里根本没有元数据:

  - 图片是从外部拖进 output 目录的(浏览器另存、手机/微信转存);
  - ComfyUI 以 ``--disable-metadata`` 启动(隐私模式), 所有产物都不写元数据;
  - 某些保存节点不写元数据。

这些情况在面板上表现为"未检测到提示词", 用户无法理解为什么。
而 ComfyUI 服务端自己保存着每次执行的完整记录(PromptQueue.history):
其中 ``prompt[2]`` 是 API 格式的提示词图, ``prompt[3].extra_pnginfo.workflow``
是 UI 格式的工作流, ``outputs`` 里则带这次执行写出的文件名。

本模块把 history 索引成 "输出文件 -> (提示词, 工作流)", 归档时按文件名回查,
做到**提示词不再依赖文件是否内嵌元数据**。

设计要点:
  - **延迟导入 server**: assets_core 仍可脱离 ComfyUI 独立测试; ComfyUI 版本变化、
    没有 ``prompt_queue`` / ``get_history`` 时索引自动停用, 不影响插件加载。
  - **只读 + 引用**: ``get_history()`` 在 prompt_id=None 时返回的是引用而非深拷贝,
    索引不复制大对象, 也不写入 history。
  - **TTL 刷新**: 默认 5 秒内最多重建一次, 只在"有文件缺元数据"时才触发, 零开销。
"""

import logging
import os
import threading
import time

log = logging.getLogger("ComfyUI-AssetManager")


class PromptHistoryIndex:
    """服务端执行历史 -> (输出文件 -> 提示词/工作流) 索引"""

    def __init__(self, max_items=500, ttl=5.0):
        self.max_items = int(max_items)
        self.ttl = float(ttl)
        self._lock = threading.Lock()
        self._by_rel = {}      # "subfolder/filename" -> (prompt, workflow)
        self._by_name = {}     # "filename"            -> (prompt, workflow)
        self._ts = 0.0
        self._ok = False
        self._entries = 0

    # ------------------------------------------------------------------ 内部
    def _fetch_history(self):
        """取最近 N 条执行历史; 服务端不可用时返回 None(不抛异常)"""
        try:
            from server import PromptServer
        except Exception:
            return None
        inst = getattr(PromptServer, "instance", None)
        if inst is None:
            return None
        queue = getattr(inst, "prompt_queue", None)
        if queue is None or not hasattr(queue, "get_history"):
            return None
        try:
            # 注意: prompt_id=None + map_function=None 时返回的是引用, 不做深拷贝
            return queue.get_history(max_items=self.max_items)
        except TypeError:
            try:  # 老版本签名不同
                return queue.get_history()
            except Exception:
                return None
        except Exception:
            return None

    @staticmethod
    def _norm_rel(subfolder, filename):
        sub = (subfolder or "").replace("\\", "/").strip("/")
        fn = (filename or "").replace("\\", "/").strip("/")
        if not fn:
            return None
        return f"{sub}/{fn}" if sub else fn

    def _rebuild(self):
        hist = self._fetch_history()
        if hist is None:
            # 服务端不可用: 保留已有索引(可能是上次抓到的), 不清空、不刷时间戳
            self._ok = False
            return
        by_rel, by_name = {}, {}
        entries = 0
        try:
            items = list(hist.values())
        except Exception:
            items = []
        # 倒序遍历: 同名文件让**最新**的执行结果覆盖旧的
        for entry in reversed(items):
            if not isinstance(entry, dict):
                continue
            entries += 1
            item = entry.get("prompt")
            # 队列项: (number, prompt_id, prompt, extra_data, outputs_to_execute[, sensitive])
            if not isinstance(item, (list, tuple)) or len(item) < 4:
                continue
            prompt = item[2]
            if not isinstance(prompt, dict):
                continue
            workflow = None
            extra = item[3]
            if isinstance(extra, dict):
                epi = extra.get("extra_pnginfo")
                if isinstance(epi, dict):
                    wf = epi.get("workflow")
                    if isinstance(wf, dict):
                        workflow = wf
            outputs = entry.get("outputs")
            if not isinstance(outputs, dict):
                continue
            for node_out in outputs.values():
                if not isinstance(node_out, dict):
                    continue
                for group in node_out.values():
                    if not isinstance(group, list):
                        continue
                    for e in group:
                        if not isinstance(e, dict):
                            continue
                        rel = self._norm_rel(e.get("subfolder"), e.get("filename"))
                        if not rel:
                            continue
                        if rel not in by_rel:
                            by_rel[rel] = (prompt, workflow)
                        base = os.path.basename(rel)
                        if base and base not in by_name:
                            by_name[base] = (prompt, workflow)
        with self._lock:
            self._by_rel = by_rel
            self._by_name = by_name
            self._entries = entries
            self._ts = time.monotonic()
            self._ok = True

    # ------------------------------------------------------------------ 接口
    def refresh(self, force=False):
        """刷新索引(TTL 内不重复刷新); 永不抛异常"""
        if force or (time.monotonic() - self._ts) >= self.ttl:
            try:
                self._rebuild()
            except Exception:
                pass

    def lookup(self, rel_path=None, src_path=None):
        """按相对路径或绝对路径查 (prompt_graph, workflow_graph); 未命中返回 None"""
        cands = []
        for p in (rel_path, src_path):
            if not p:
                continue
            p = str(p).replace("\\", "/")
            cands.append(p)
            cands.append(os.path.basename(p))
        with self._lock:
            by_rel, by_name = self._by_rel, self._by_name
        for c in cands:
            if c and c in by_rel:
                return by_rel[c]
        for c in cands:
            if not c:
                continue
            base = os.path.basename(c)
            if base in by_name:
                return by_name[base]
        return None

    def stats(self):
        with self._lock:
            return {
                "ok": self._ok,
                "entries": self._entries,
                "indexed_rel": len(self._by_rel),
                "indexed_names": len(self._by_name),
                "max_items": self.max_items,
                "ttl": self.ttl,
            }
