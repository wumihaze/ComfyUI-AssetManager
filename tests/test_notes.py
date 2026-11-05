"""手动备注测试。

备注是给"提不出提示词"的产物(网图、截图、别人转存的图)补一句自己的说明:
只写归档目录的 info.json, 不动媒体文件、不动目录结构, 会参与前端搜索匹配。
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import assets_core

CFG = {"thumb_width": 256}


def write_media(path, data=b"\x89PNG\r\n\x1a\nfake-image-bytes"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def run_dirs(archive_dir):
    arch = Path(archive_dir)
    return [p.relative_to(arch).as_posix()
            for p in sorted(arch.glob("*/*")) if (p / "info.json").is_file()]


def read_info(archive_dir, rel):
    return json.loads((Path(archive_dir) / rel / "info.json").read_text(encoding="utf-8"))


class NoteBasicsTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        root = Path(self._td.name)
        self.out = root / "output"
        self.arch = root / "archive"
        self.out.mkdir()
        self.arch.mkdir()
        self.state = {"__baseline_done__": True}

    def tearDown(self):
        self._td.cleanup()

    def archive_one(self, name="a.png"):
        write_media(self.out / name)
        assets_core.scan_all(self.out, self.arch, self.state, CFG)
        return run_dirs(self.arch)[0]

    def test_set_and_read_note(self):
        rel = self.archive_one()
        res = assets_core.set_run_note(self.arch, rel, "从官网存的参考图")
        self.assertTrue(res["ok"])
        self.assertEqual(res["note"], "从官网存的参考图")
        info = read_info(self.arch, rel)
        self.assertEqual(info["note"], "从官网存的参考图")
        self.assertIn("note_updated_at", info)
        # list_runs 要能带出来
        runs = assets_core.list_runs(self.arch)
        self.assertEqual(runs[0]["note"], "从官网存的参考图")

    def test_runs_without_note_report_empty_string(self):
        self.archive_one()
        self.assertEqual(assets_core.list_runs(self.arch)[0]["note"], "")

    def test_empty_note_clears_the_field(self):
        rel = self.archive_one()
        assets_core.set_run_note(self.arch, rel, "临时说明")
        res = assets_core.set_run_note(self.arch, rel, "   ")
        self.assertTrue(res["ok"])
        self.assertEqual(res["note"], "")
        info = read_info(self.arch, rel)
        self.assertNotIn("note", info)
        self.assertNotIn("note_updated_at", info)
        self.assertEqual(assets_core.list_runs(self.arch)[0]["note"], "")

    def test_note_does_not_touch_the_media_file(self):
        rel = self.archive_one()
        info = read_info(self.arch, rel)
        media = Path(self.arch) / rel / info["media"]
        before = (media.stat().st_size, media.stat().st_mtime_ns, media.read_bytes())
        assets_core.set_run_note(self.arch, rel, "备注")
        after = (media.stat().st_size, media.stat().st_mtime_ns, media.read_bytes())
        self.assertEqual(before, after)

    def test_length_boundary(self):
        rel = self.archive_one()
        self.assertTrue(assets_core.set_run_note(self.arch, rel, "字" * 500)["ok"])
        res = assets_core.set_run_note(self.arch, rel, "字" * 501)
        self.assertFalse(res["ok"])
        self.assertIn("note too long", res["error"])
        # 超长时不能把原来的备注写坏
        self.assertEqual(read_info(self.arch, rel)["note"], "字" * 500)

    def test_non_string_note_is_rejected(self):
        rel = self.archive_one()
        for bad in (None, 5, ["x"], {"a": 1}, True):
            res = assets_core.set_run_note(self.arch, rel, bad)
            self.assertFalse(res["ok"], bad)
            self.assertEqual(res["error"], "note must be a string")

    def test_newlines_kept_and_control_chars_stripped(self):
        rel = self.archive_one()
        res = assets_core.set_run_note(self.arch, rel, "第一行\r\n第二行\x00\x07\t末尾  ")
        self.assertTrue(res["ok"])
        self.assertEqual(res["note"], "第一行\n第二行\t末尾")
        self.assertEqual(read_info(self.arch, rel)["note"], "第一行\n第二行\t末尾")

    def test_unicode_and_markup_are_stored_verbatim(self):
        rel = self.archive_one()
        text = '<b>不要当 HTML</b> 🎨 \u2028 分隔'
        self.assertTrue(assets_core.set_run_note(self.arch, rel, text)["ok"])
        # 尖括号/emoji 原样保存(前端用 textContent 渲染); U+2028 归一成普通换行
        self.assertEqual(read_info(self.arch, rel)["note"],
                         '<b>不要当 HTML</b> 🎨 \n 分隔')

    def test_note_survives_a_rescan(self):
        rel = self.archive_one()
        assets_core.set_run_note(self.arch, rel, "扫描不能把它冲掉")
        assets_core.scan_all(self.out, self.arch, self.state, CFG)
        self.assertEqual(read_info(self.arch, rel)["note"], "扫描不能把它冲掉")

    def test_note_survives_a_move_in_output(self):
        """在 output 里改名后走的是"就地更新原记录", 备注必须保留。"""
        rel = self.archive_one()
        assets_core.set_run_note(self.arch, rel, "移动后还在")
        os.replace(self.out / "a.png", self.out / "b.png")
        assets_core.scan_all(self.out, self.arch, self.state, CFG)
        self.assertEqual(len(run_dirs(self.arch)), 1)
        info = read_info(self.arch, run_dirs(self.arch)[0])
        self.assertEqual(info["source_rel"], "b.png")
        self.assertEqual(info["note"], "移动后还在")


class NoteInputTests(unittest.TestCase):
    """run_id / info.json 的坏输入不能抛异常, 也不能写到归档目录之外。"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.arch = Path(self._td.name) / "archive"
        self.arch.mkdir()
        self.outside = Path(self._td.name) / "outside"
        self.outside.mkdir()
        (self.outside / "info.json").write_text('{"source_rel": "x.png", "media": "x.png"}',
                                                encoding="utf-8")

    def tearDown(self):
        self._td.cleanup()

    def test_bad_run_ids_are_rejected(self):
        bad = ["", "   ", "../outside", "/abs/path", "a/b/c",
               "2026-11-05/../../outside", ".", ".."]
        for run_id in bad:
            res = assets_core.set_run_note(self.arch, run_id, "x")
            self.assertFalse(res["ok"], run_id)
            self.assertEqual(res["error"], "invalid path", run_id)
        for bad_type in (None, 5, ["a"], {}):
            res = assets_core.set_run_note(self.arch, bad_type, "x")
            self.assertFalse(res["ok"], bad_type)
            self.assertEqual(res["error"], "invalid path", bad_type)
        # 归档目录外那份 info.json 必须原封不动
        self.assertEqual(json.loads((self.outside / "info.json").read_text(encoding="utf-8")),
                         {"source_rel": "x.png", "media": "x.png"})

    def test_missing_info_json(self):
        (self.arch / "2026-11-05" / "empty-run").mkdir(parents=True)
        res = assets_core.set_run_note(self.arch, "2026-11-05/empty-run", "x")
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "missing info.json")

    def test_broken_info_json(self):
        run = self.arch / "2026-11-05" / "broken"
        run.mkdir(parents=True)
        (run / "info.json").write_text("{not json", encoding="utf-8")
        res = assets_core.set_run_note(self.arch, "2026-11-05/broken", "x")
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "unreadable info.json")
        # 坏文件不能被改成别的内容
        self.assertEqual((run / "info.json").read_text(encoding="utf-8"), "{not json")

    def test_non_dict_info_json(self):
        run = self.arch / "2026-11-05" / "listlike"
        run.mkdir(parents=True)
        (run / "info.json").write_text("[1, 2, 3]", encoding="utf-8")
        res = assets_core.set_run_note(self.arch, "2026-11-05/listlike", "x")
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "invalid info.json")

    def test_unwritable_run_dir(self):
        run = self.arch / "2026-11-05" / "ro"
        run.mkdir(parents=True)
        (run / "info.json").write_text('{"source_rel": "x.png", "media": "x.png"}',
                                       encoding="utf-8")
        real_replace = os.replace

        def boom(*a, **k):
            raise OSError("disk full")

        os.replace = boom
        try:
            res = assets_core.set_run_note(self.arch, "2026-11-05/ro", "x")
        finally:
            os.replace = real_replace
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "Cannot write note")


if __name__ == "__main__":
    unittest.main()
