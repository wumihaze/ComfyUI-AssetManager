"""安全回归测试。

关注点: 恶意 / 畸形输入不能
  1) 读写归档目录之外的任何文件(路径穿越、符号链接、state 文件被篡改),
  2) 让接口抛 500 或把绝对路径/堆栈回给前端,
  3) 用超大/超深/类型错乱的 JSON 拖垮进程。

路由层测试把插件装进一个桩环境里 import: 不启动后台监视线程,
归档目录指向临时目录, 因此不会碰到真实数据。
"""

import asyncio
import itertools
import json
import os
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_DIR))

import assets_core

CFG = {"thumb_width": 256}

_seq = itertools.count(1)


def uniq(prefix="分类"):
    """分类名在同一个归档目录里唯一, 避免用例之间互相撞名。"""
    return "%s%d" % (prefix, next(_seq))


def write_bytes(path, data=b"\x89PNG\r\n\x1a\nfake"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def make_run(archive_dir, rel_dir, source_rel="a.png", extra=None):
    run_dir = Path(archive_dir) / rel_dir
    run_dir.mkdir(parents=True, exist_ok=True)
    info = {"run_id": run_dir.name, "generated_at": "2026-11-05T10:00:00",
            "source_rel": source_rel, "media": Path(source_rel).name, "kind": "image"}
    if extra:
        info.update(extra)
    (run_dir / "info.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    (run_dir / info["media"]).write_bytes(b"x")
    return run_dir


class CategoryInputTests(unittest.TestCase):
    """分类接口的输入面: 类型错乱、越界值、注入、超限。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.td = self._td.name

    def tearDown(self):
        self._td.cleanup()

    def write_categories(self, payload):
        (Path(self.td) / "categories.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def ids(self):
        return [c["id"] for c in assets_core.load_categories(self.td)["categories"]]

    # ---- move / pin 的参数校验 ----

    def test_move_rejects_everything_that_is_not_up_or_down(self):
        cid = assets_core.create_category(self.td, "A")["category"]["id"]
        for bad in (None, "", "UP", "Up", " up", "up ", "updown", ["up"], {"d": "up"},
                    0, 1, True, False, 3.5, "x" * 5000):
            r = assets_core.move_category(self.td, cid, bad)
            self.assertFalse(r["ok"], "direction=%r 竟然被接受了" % (bad,))
            self.assertEqual(r["error"], "Invalid direction")

    def test_move_rejects_bad_ids(self):
        assets_core.create_category(self.td, "A")
        for bad in (None, "", 123, [], {}, "0" * 5000, "../../etc/passwd"):
            self.assertFalse(assets_core.move_category(self.td, bad, "up")["ok"])

    def test_pin_rejects_non_boolean(self):
        cid = assets_core.create_category(self.td, "A")["category"]["id"]
        for bad in (None, 0, 1, "true", "false", [], {}, 1.0):
            r = assets_core.set_category_pinned(self.td, cid, bad)
            self.assertFalse(r["ok"], "pinned=%r 竟然被接受了" % (bad,))
            self.assertEqual(r["error"], "pinned must be a boolean")

    def test_move_and_pin_do_not_mutate_on_reject(self):
        cid = assets_core.create_category(self.td, "A")["category"]["id"]
        before = (Path(self.td) / "categories.json").read_bytes()
        assets_core.move_category(self.td, cid, "sideways")
        assets_core.set_category_pinned(self.td, cid, "yes")
        self.assertEqual((Path(self.td) / "categories.json").read_bytes(), before)

    # ---- categories.json 被手工改坏 ----

    def test_hostile_order_values_do_not_crash(self):
        self.write_categories({"categories": [
            {"id": "a", "name": "A", "order": 10 ** 40},
            {"id": "b", "name": "B", "order": -10 ** 40},
            {"id": "c", "name": "C", "order": True},          # bool 是 int 子类
            {"id": "d", "name": "D", "order": "3"},
            {"id": "e", "name": "E", "order": 3.9},
            {"id": "f", "name": "F", "order": None},
            {"id": "g", "name": "G", "order": {"x": 1}},
        ]})
        items = assets_core.load_categories(self.td)["categories"]
        self.assertEqual(len(items), 7)
        # 无论输入多离谱, 输出都是每层 0..n-1 的连续值
        self.assertEqual([c["order"] for c in items], list(range(7)))

    def test_hostile_pinned_values_are_coerced_to_bool(self):
        self.write_categories({"categories": [
            {"id": "a", "name": "A", "pinned": "yes"},
            {"id": "b", "name": "B", "pinned": 0},
            {"id": "c", "name": "C", "pinned": []},
        ]})
        items = assets_core.load_categories(self.td)["categories"]
        for c in items:
            self.assertIsInstance(c["pinned"], bool)

    def test_parent_pointing_at_itself_or_outside_is_dropped(self):
        self.write_categories({"categories": [
            {"id": "a", "name": "A", "parent": "a"},
            {"id": "b", "name": "B", "parent": "../../../etc"},
            {"id": "c", "name": "C", "parent": 123},
            {"id": "d", "name": "D", "parent": "a"},   # a 是根, 合法
            {"id": "e", "name": "E", "parent": "d"},   # 第三层 → 压平
        ]})
        items = {c["id"]: c for c in assets_core.load_categories(self.td)["categories"]}
        self.assertIsNone(items["a"]["parent"])
        self.assertIsNone(items["b"]["parent"])
        self.assertIsNone(items["c"]["parent"])
        self.assertEqual(items["d"]["parent"], "a")
        self.assertIsNone(items["e"]["parent"])

    def test_duplicate_ids_are_collapsed(self):
        self.write_categories({"categories": [
            {"id": "dup", "name": "第一个"},
            {"id": "dup", "name": "第二个"},
        ]})
        items = assets_core.load_categories(self.td)["categories"]
        self.assertEqual([c["name"] for c in items], ["第一个"])

    def test_corrupt_and_wrong_shaped_files(self):
        for payload in ("not json", "[]", "{}", '{"categories": "x"}',
                        '{"categories": [1, "a", null, []]}', "null", ""):
            (Path(self.td) / "categories.json").write_text(payload, encoding="utf-8")
            self.assertEqual(assets_core.load_categories(self.td)["categories"], [])

    def test_deeply_nested_json_does_not_blow_up(self):
        deep = "[" * 400 + "]" * 400
        (Path(self.td) / "categories.json").write_text(
            '{"categories": %s}' % deep, encoding="utf-8")
        self.assertIsInstance(assets_core.load_categories(self.td)["categories"], list)

    # ---- 名称注入 ----

    def test_name_injection_is_stored_verbatim_but_neutralised(self):
        payload = '"><script>alert(1)</script>'
        r = assets_core.create_category(self.td, payload)
        self.assertTrue(r["ok"])
        self.assertEqual(r["category"]["name"], payload)   # 原样保存, 前端用 textContent 渲染
        # id 是自己生成的, 与名字无关; 名字从不参与路径拼接
        self.assertRegex(r["category"]["id"], r"^[0-9a-f]{8}$")
        self.assertNotIn("..", r["category"]["id"])

    def test_name_with_path_separators_stays_a_label(self):
        """名字里带 / 或 \\ 只是文字, 不会变成路径, 也不会让后续操作写错目录。"""
        cid = assets_core.create_category(self.td, "a/b\\c/../d")["category"]["id"]
        self.assertTrue(assets_core.set_category_pinned(self.td, cid, True)["ok"])
        self.assertTrue(assets_core.move_category(self.td, cid, "down")["ok"])
        self.assertEqual([p.name for p in Path(self.td).iterdir()], ["categories.json"])

    def test_control_characters_and_newlines_are_stripped(self):
        r = assets_core.create_category(self.td, "a\x00b\x1f\nc\r\td")
        self.assertTrue(r["ok"])
        self.assertEqual(r["category"]["name"], "abcd")

    def test_name_length_is_capped(self):
        r = assets_core.create_category(self.td, "长" * 500)
        self.assertEqual(len(r["category"]["name"]), assets_core.CATEGORY_NAME_MAX)

    def test_blank_and_non_string_names_rejected(self):
        for bad in ("", "   ", "\n\t", None, 123, [], {}, True):
            self.assertFalse(assets_core.create_category(self.td, bad)["ok"])

    # ---- 数量上限 ----

    def test_create_stops_at_the_limit(self):
        self.write_categories({"categories": [
            {"id": "c%d" % i, "name": "分类%d" % i, "order": i}
            for i in range(assets_core.CATEGORY_LIMIT)
        ]})
        r = assets_core.create_category(self.td, "再来一个")
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "Too many categories")

    def test_reading_a_hand_edited_oversized_file_does_not_drop_entries(self):
        """超过上限的文件只读不写时不能被静默截断(否则下次保存就丢数据)。"""
        n = assets_core.CATEGORY_LIMIT + 5
        self.write_categories({"categories": [
            {"id": "c%d" % i, "name": "分类%d" % i, "order": i} for i in range(n)
        ]})
        self.assertEqual(len(assets_core.load_categories(self.td)["categories"]), n)
        cid = "c0"
        assets_core.rename_category(self.td, cid, "改个名")
        self.assertEqual(len(assets_core.load_categories(self.td)["categories"]), n)


class ArchivePathSafetyTests(unittest.TestCase):
    """去重 / 归档链路上的路径安全。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        root = Path(self._td.name)
        self.out = root / "output"
        self.arch = root / "archive"
        self.outside = root / "outside"
        self.out.mkdir()
        self.arch.mkdir()
        self.outside.mkdir()
        self.state = {}

    def tearDown(self):
        self._td.cleanup()

    def archive(self, rel):
        return assets_core.archive_file(rel, self.out / rel, self.arch, self.state,
                                        CFG, source_root=self.out)

    def test_tampered_state_index_cannot_target_files_outside_the_archive(self):
        """state 里的 __content__ 是人可改的: 指向归档外时必须拒绝, 且不能改写那个文件。"""
        victim = self.outside / "victim"
        victim.mkdir()
        victim_info = victim / "info.json"
        victim_info.write_text('{"keep": "me"}', encoding="utf-8")

        write_bytes(self.out / "a.png", b"payload")
        h = assets_core.file_content_hash(self.out / "a.png")
        for evil in ("../outside/victim", "../../outside/victim", str(victim),
                     "/etc", "..", ".", "a/b/c", "..\\..\\outside\\victim",
                     "2026-11-05/../../outside/victim", ""):
            self.state = {"__content__": {h: evil}}
            r = assets_core.archive_file("a.png", self.out / "a.png", self.arch,
                                         self.state, CFG, source_root=self.out)
            self.assertIsNotNone(r, "恶意的 prev_rel 让归档整个失败了: %r" % (evil,))
            self.assertFalse(r.get("merged"), "恶意的 prev_rel 被合并了: %r" % (evil,))
            self.assertEqual(victim_info.read_text(encoding="utf-8"), '{"keep": "me"}')

    def test_merge_ignores_index_pointing_at_a_file_not_a_dir(self):
        write_bytes(self.arch / "2026-11-05", b"i am a file")
        write_bytes(self.out / "a.png", b"payload")
        h = assets_core.file_content_hash(self.out / "a.png")
        self.state["__content__"] = {h: "2026-11-05/x"}
        r = self.archive("a.png")
        # 记录不了(日期位置被文件占住), 但不能抛异常, 也不能改坏那个文件
        self.assertIsNone(r)
        self.assertEqual((self.arch / "2026-11-05").read_bytes(), b"i am a file")

    def test_scan_survives_a_blocked_date_dir(self):
        """某一天的目录被同名文件占住时, 扫描不能整体崩掉(路由会 500)。"""
        write_bytes(self.arch / "2026-11-05", b"i am a file")
        self.state["__baseline_done__"] = True
        write_bytes(self.out / "a.png", b"payload")
        self.assertEqual(assets_core.scan_all(self.out, self.arch, self.state, CFG), 0)
        self.assertNotIn("a.png", self.state)

    def test_source_outside_output_is_refused(self):
        stray = write_bytes(self.outside / "stray.png", b"payload")
        self.assertIsNone(assets_core.archive_file(
            "stray.png", stray, self.arch, self.state, CFG, source_root=self.out))

    def test_symlinked_source_is_refused(self):
        write_bytes(self.outside / "secret.png", b"payload")
        link = self.out / "link.png"
        try:
            os.symlink(self.outside / "secret.png", link)
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("symlink not permitted on this platform")
        self.assertIsNone(assets_core.archive_file(
            "link.png", link, self.arch, self.state, CFG, source_root=self.out))

    def test_symlinked_run_dir_is_not_merged_into(self):
        target = self.outside / "target"
        make_run(self.outside, "target", "a.png")
        (self.arch / "2026-11-05").mkdir(parents=True, exist_ok=True)
        link = self.arch / "2026-11-05" / "run"
        try:
            os.symlink(target, link, target_is_directory=True)
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("symlink not permitted on this platform")
        write_bytes(self.out / "a.png", b"payload")
        h = assets_core.file_content_hash(self.out / "a.png")
        self.state["__content__"] = {h: "2026-11-05/run"}
        r = self.archive("a.png")
        self.assertFalse(r.get("merged"))
        self.assertNotIn("moved_at", json.loads(
            (target / "info.json").read_text(encoding="utf-8")))

    def test_scan_skips_symlinked_dirs_and_files(self):
        self.state["__baseline_done__"] = True
        write_bytes(self.outside / "secret.png", b"payload")
        try:
            os.symlink(self.outside, self.out / "linked_dir", target_is_directory=True)
            os.symlink(self.outside / "secret.png", self.out / "linked.png")
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("symlink not permitted on this platform")
        self.assertEqual(assets_core.scan_all(self.out, self.arch, self.state, CFG), 0)

    def test_oversized_file_skips_fingerprinting(self):
        big = write_bytes(self.out / "big.png", b"0" * 64)
        self.assertIsNone(assets_core.file_content_hash(big, limit=8))
        # archive_file 用的是默认上限, 临时把它压到 8 字节来验证"大文件不写 content_hash"
        real = assets_core.file_content_hash.__defaults__
        assets_core.file_content_hash.__defaults__ = (8,)
        try:
            r = assets_core.archive_file("big.png", big, self.arch, self.state, CFG,
                                         source_root=self.out)
        finally:
            assets_core.file_content_hash.__defaults__ = real
        self.assertIn("dir", r)
        info = json.loads((self.arch / r["dir"] / "info.json").read_text(encoding="utf-8"))
        self.assertNotIn("content_hash", info)


# ---------------------------------------------------------------------------
# 路由层: 把插件装进桩环境 import, 直接调用 aiohttp 处理函数
# ---------------------------------------------------------------------------

class _Routes:
    def __init__(self):
        self.handlers = {}

    def _register(self, path):
        def deco(fn):
            self.handlers[path] = fn
            return fn
        return deco

    def get(self, path):
        return self._register(path)

    def post(self, path):
        return self._register(path)


class _Req:
    def __init__(self, payload=None, query=None, headers=None):
        self._payload = payload
        self.query = query or {}
        self.headers = headers or {}
        self.rel_url = types.SimpleNamespace(query=self.query)

    async def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _import_plugin(archive_dir, output_dir):
    """在桩环境里 import 插件: 不启动监视线程, 归档目录指向临时目录。"""
    routes = _Routes()
    server = types.ModuleType("server")
    server.PromptServer = types.SimpleNamespace(
        instance=types.SimpleNamespace(routes=routes))
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_output_directory = lambda: str(output_dir)
    folder_paths.set_output_directory = lambda p: None
    folder_paths.get_user_directory = lambda: str(Path(archive_dir) / "user")
    sys.modules["server"] = server
    sys.modules["folder_paths"] = folder_paths

    cfg = dict(assets_core.DEFAULT_CONFIG)
    cfg.update({"archive_dir": str(archive_dir), "backup_dir": str(Path(archive_dir) / "bak")})
    real_load_config = assets_core.load_config
    assets_core.load_config = lambda base_dir: dict(cfg)

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
            "asset_manager_plugin_under_test", str(PLUGIN_DIR / "__init__.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        threading.Thread = real_thread
        assets_core.load_config = real_load_config
    return mod, routes


class RouteSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._td = tempfile.TemporaryDirectory()
        root = Path(cls._td.name)
        cls.arch = root / "archive"
        cls.out = root / "output"
        cls.arch.mkdir()
        cls.out.mkdir()
        cls.mod, cls.routes = _import_plugin(cls.arch, cls.out)
        cls.mod._arch = str(cls.arch)

    @classmethod
    def tearDownClass(cls):
        cls._td.cleanup()

    def setUp(self):
        # 写配置会落到插件目录, 测试里换掉
        self._real_save_config = assets_core.save_config
        assets_core.save_config = lambda *a, **k: None

    def tearDown(self):
        assets_core.save_config = self._real_save_config

    def call_raw(self, path, payload=None, query=None, headers=None):
        handler = self.routes.handlers[path]
        return asyncio.run(handler(_Req(payload, query, headers)))

    def call(self, path, payload=None, query=None, headers=None):
        resp = self.call_raw(path, payload, query, headers)
        return resp.status, json.loads(resp.text)

    # ---- /asset/category ----

    def test_non_object_body(self):
        for body in ([], "x", 5, None, True):
            status, data = self.call("/asset/category", body)
            self.assertEqual(status, 200)
            self.assertFalse(data["ok"])

    def test_unparsable_json_falls_back_to_empty_body(self):
        status, data = self.call("/asset/category", ValueError("boom"))
        self.assertEqual(status, 200)
        self.assertFalse(data["ok"])

    def test_type_confusion_on_every_field(self):
        cases = [
            {"action": "create", "name": 123},
            {"action": "create", "name": ["x"]},
            {"action": "create", "name": "ok", "parent": 1},
            {"action": "rename", "id": {}, "name": "x"},
            {"action": "delete", "id": []},
            {"action": "move", "id": "x", "direction": 1},
            {"action": "pin", "id": "x", "pinned": "true"},
            {"action": "pin", "id": "x", "pinned": 1},
            {"action": ["create"], "name": "x"},
        ]
        for body in cases:
            status, data = self.call("/asset/category", body)
            self.assertEqual(status, 200, body)
            self.assertFalse(data["ok"], body)
            self.assertIsInstance(data.get("error"), str, body)

    def test_pin_without_flag_is_rejected(self):
        cid = assets_core.create_category(str(self.arch), uniq())["category"]["id"]
        status, data = self.call("/asset/category", {"action": "pin", "id": cid})
        self.assertFalse(data["ok"])
        self.assertEqual(data["error"], "pinned must be a boolean")

    def test_unknown_action(self):
        status, data = self.call("/asset/category", {"action": "drop table"})
        self.assertEqual(status, 200)
        self.assertFalse(data["ok"])
        self.assertEqual(data["error"], "Unknown action")

    def test_full_move_and_pin_round_trip(self):
        na, nb = uniq("甲"), uniq("乙")
        a = assets_core.create_category(str(self.arch), na)["category"]["id"]
        b = assets_core.create_category(str(self.arch), nb)["category"]["id"]
        _, data = self.call("/asset/category", {"action": "move", "id": b, "direction": "up"})
        self.assertTrue(data["ok"])
        self.assertEqual([c["name"] for c in data["categories"]][-2:], [nb, na])
        _, data = self.call("/asset/category", {"action": "pin", "id": a, "pinned": True})
        self.assertTrue(data["ok"])
        self.assertEqual([c["name"] for c in data["categories"]][:2], [na, nb])
        _, data = self.call("/asset/category", {"action": "pin", "id": a, "pinned": False})
        self.assertEqual([c["name"] for c in data["categories"]][-2:], [nb, na])

    # ---- 失败时不能泄露路径 ----

    def test_error_message_never_leaks_absolute_paths(self):
        """归档目录不可写时, 返回的 error 里不能出现真实路径。"""
        real = self.mod._arch
        self.mod._arch = str(Path(self._td.name) / "no_such_dir" / "deeper")
        try:
            status, data = self.call("/asset/category", {"action": "create", "name": "x"})
            self.assertEqual(status, 200)
            self.assertFalse(data["ok"])
            text = json.dumps(data, ensure_ascii=False)
            self.assertNotIn(self._td.name, text)
            self.assertNotIn("no_such_dir", text)
            self.assertNotIn("Traceback", text)
        finally:
            self.mod._arch = real

    # ---- /asset/assign ----

    def test_assign_rejects_oversized_and_malformed_input(self):
        for body in ({"run_ids": "x"}, {"run_ids": {"a": 1}},
                     {"run_ids": ["r%d" % i for i in range(600)]},
                     {"run_ids": ["a"], "category": 5}):
            status, data = self.call("/asset/assign", body)
            self.assertEqual(status, 200)
            self.assertFalse(data["ok"], body)
            self.assertNotIn(self._td.name, json.dumps(data))

    def test_assign_filters_non_string_run_ids(self):
        status, data = self.call("/asset/assign", {"run_ids": [1, None, {}, "ok"]})
        self.assertEqual(status, 200)
        # 非字符串被丢弃, 不会抛错
        self.assertTrue(data["ok"])

    # ---- /asset/note: 手动备注 ----

    def test_note_rejects_type_confusion(self):
        for body in ({"run_id": 1, "note": "x"}, {"run_id": ["a"], "note": "x"},
                     {"run_id": "2026-11-05/r1", "note": 5},
                     {"run_id": "2026-11-05/r1", "note": ["x"]},
                     {"note": "x"}, {"run_id": "2026-11-05/r1"}):
            status, data = self.call("/asset/note", body)
            self.assertEqual(status, 200, body)
            self.assertFalse(data["ok"], body)
            self.assertIsInstance(data.get("error"), str, body)

    def test_note_rejects_traversal_and_oversized_note(self):
        make_run(self.arch, "2026-11-05/note-target")
        for run_id in ("../../etc", "/abs/path"):
            status, data = self.call("/asset/note", {"run_id": run_id, "note": "x"})
            self.assertEqual(status, 200, run_id)
            self.assertFalse(data["ok"], run_id)
            self.assertEqual(data["error"], "invalid path", run_id)
        # 日期目录本身不是一条记录(含 ../ 归一后落到日期目录的情况):
        # 不会写到它下面的 info.json
        for run_id in ("2026-11-05", "2026-11-05/../2026-11-05"):
            status, data = self.call("/asset/note", {"run_id": run_id, "note": "x"})
            self.assertFalse(data["ok"], run_id)
            self.assertEqual(data["error"], "missing info.json", run_id)
        status, data = self.call(
            "/asset/note", {"run_id": "2026-11-05/note-target", "note": "x" * 501})
        self.assertFalse(data["ok"])
        self.assertIn("note too long", data["error"])
        # 报错不回显绝对路径
        self.assertNotIn(self._td.name, json.dumps(data))

    def test_note_round_trip_over_route(self):
        make_run(self.arch, "2026-11-05/note-rt")
        status, data = self.call(
            "/asset/note", {"run_id": "2026-11-05/note-rt", "note": "参考图，来自官网"})
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"], data)
        self.assertEqual(data["note"], "参考图，来自官网")
        info = json.loads((self.arch / "2026-11-05/note-rt/info.json").read_text(encoding="utf-8"))
        self.assertEqual(info["note"], "参考图，来自官网")
        # 清空
        status, data = self.call("/asset/note", {"run_id": "2026-11-05/note-rt", "note": ""})
        self.assertTrue(data["ok"])
        info = json.loads((self.arch / "2026-11-05/note-rt/info.json").read_text(encoding="utf-8"))
        self.assertNotIn("note", info)

    # ---- 只读接口在异常配置下也不能 500 ----

    def test_categories_endpoint_survives_missing_archive(self):
        real = self.mod._arch
        self.mod._arch = str(Path(self._td.name) / "gone")
        try:
            status, data = self.call("/asset/categories")
            self.assertEqual(status, 200)
            self.assertEqual(data["categories"], [])
        finally:
            self.mod._arch = real

    # ---- 跨站写请求 ----

    def test_cross_site_origin_is_rejected_on_writes(self):
        host = {"Host": "127.0.0.1:8188"}
        for origin in ("https://evil.example", "http://127.0.0.1:9999",
                       "http://localhost:8188", "http://127.0.0.1:8188.evil.example"):
            status, data = self.call("/asset/category", {"action": "create", "name": "x"},
                                     headers=dict(host, Origin=origin))
            self.assertEqual(status, 403, origin)
            self.assertFalse(data["ok"])

    def test_same_origin_and_non_browser_requests_pass(self):
        ok_cases = [
            {"Host": "127.0.0.1:8188", "Origin": "http://127.0.0.1:8188"},
            {"Host": "127.0.0.1:8188", "Origin": "HTTP://127.0.0.1:8188"},
            {"Host": "127.0.0.1:8188"},                       # 命令行/脚本
            {"Host": "127.0.0.1:8188", "Origin": "null"},     # file:// 页面
            {"Host": "127.0.0.1:8188", "Origin": "app://comfyui"},
        ]
        for headers in ok_cases:
            body = {"action": "create", "name": uniq("同源")}
            status, data = self.call("/asset/category", body, headers=headers)
            self.assertEqual(status, 200, headers)
            self.assertTrue(data["ok"], headers)

    def test_every_mutating_route_is_guarded(self):
        guarded = ["/asset/set_output_dir", "/asset/set_config", "/asset/delete",
                   "/asset/delete_batch", "/asset/category", "/asset/assign",
                   "/asset/note", "/asset/scan", "/asset/backup"]
        for path in guarded:
            status, _ = self.call(path, {}, headers={"Host": "127.0.0.1:8188",
                                                     "Origin": "https://evil.example"})
            self.assertEqual(status, 403, path)

    # ---- /asset/file: 只服务清单里列出的媒体文件 ----

    def test_file_endpoint_only_serves_listed_media(self):
        make_run(self.arch, "2026-11-05/run-1", "角色/图.png")
        resp = self.call_raw("/asset/file", query={"p": "2026-11-05/run-1/图.png"})
        self.assertEqual(resp.status, 200)

        for bad in ("../../../Windows/win.ini",
                    "..\\..\\..\\Windows\\win.ini",
                    "C:/Windows/win.ini",
                    "/etc/passwd",
                    "2026-11-05/run-1/info.json",
                    "2026-11-05/run-1/../../archive_state.json",
                    "archive_state.json",
                    "2026-11-05/run-1/thumb.jpg",     # 没有缩略图
                    "2026-11-05/run-1",
                    ""):
            got = self.call_raw("/asset/file", query={"p": bad})
            self.assertEqual(got.status, 404, bad)

    def test_file_endpoint_rejects_non_string_param(self):
        got = self.call_raw("/asset/file", query={"p": ["x"]})
        self.assertEqual(got.status, 400)

    def test_workflow_endpoint_refuses_media_files(self):
        make_run(self.arch, "2026-11-05/run-2", "角色/图2.png")
        self.assertEqual(
            self.call_raw("/asset/workflow", query={"p": "2026-11-05/run-2/图2.png"}).status, 404)

    # ---- /asset/browse_dir: 不能列出允许范围之外的内容 ----

    def test_browse_rejects_paths_outside_the_allowed_roots(self):
        for bad in ("C:\\Windows", "C:\\Windows\\System32", "\\\\server\\share"):
            status, data = self.call("/asset/browse_dir", query={"path": bad})
            self.assertEqual(status, 200, bad)
            self.assertFalse(data["ok"], bad)
            self.assertNotIn("Traceback", json.dumps(data))

    def test_browse_rejects_a_sibling_of_the_allowed_root(self):
        """允许目录的"邻居"必须被拒 —— 这正是防目录枚举的关键。"""
        sibling = Path(self._td.name).parent / "not_on_the_chain"
        sibling.mkdir(exist_ok=True)
        try:
            status, data = self.call("/asset/browse_dir", query={"path": str(sibling)})
            self.assertEqual(status, 200)
            self.assertFalse(data["ok"])
            self.assertEqual(data["error"], "Directory is outside the allowed browse scope")
        finally:
            sibling.rmdir()

    def test_browse_on_a_drive_root_only_reveals_the_chain(self):
        """盘符根可以当起点, 但只能看到"通往允许目录"的那一级, 不能列出同级目录。"""
        abs_td = os.path.abspath(self._td.name)
        drive_root = os.path.splitdrive(abs_td)[0] + os.sep
        first = Path(abs_td).parts[1]           # 例如 Users
        status, data = self.call("/asset/browse_dir", query={"path": drive_root})
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertEqual(data["dirs"], [first])

    def test_browse_rejects_oversized_and_non_string_paths(self):
        _, data = self.call("/asset/browse_dir", query={"path": "a" * 5000})
        self.assertFalse(data["ok"])
        self.assertEqual(data["error"], "path too long")
        _, data = self.call("/asset/browse_dir", query={"path": ["C:"]})
        self.assertFalse(data["ok"])

    # ---- /asset/set_config: 目录不能互相包含 ----

    def test_set_config_refuses_overlapping_dirs(self):
        before = dict(self.mod._cfg)
        _, data = self.call("/asset/set_config", {
            "archive_dir": str(self.arch),
            "backup_dir": str(self.arch / "bak"),
        })
        self.assertTrue(data["errors"])
        self.assertTrue(any("must not overlap" in e for e in data["errors"]))
        # 冲突的键不会被写进运行时配置
        self.assertEqual(self.mod._cfg.get("archive_dir"), before.get("archive_dir"))

    def test_set_config_refuses_unknown_keys_and_bad_types(self):
        _, data = self.call("/asset/set_config", {
            "evil_key": "x", "interval_sec": 10 ** 9, "auto_archive": "false",
        })
        self.assertTrue(any("not allowed" in e for e in data["errors"]))
        self.assertTrue(any("interval_sec" in e for e in data["errors"]))
        self.assertTrue(any("auto_archive" in e for e in data["errors"]))
        self.assertIs(self.mod._cfg.get("auto_archive"), True)
        self.assertNotIn("evil_key", self.mod._cfg)


if __name__ == "__main__":
    unittest.main()
