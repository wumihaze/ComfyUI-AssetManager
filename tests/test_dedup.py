"""防重复归档测试: 同一份内容换路径(移动/改名)不再归档第二份。"""

import json
import os
import shutil
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
    """归档里所有含 info.json 的记录目录(按相对路径排序)。"""
    arch = Path(archive_dir)
    out = []
    for p in sorted(arch.glob("*/*")):
        if (p / "info.json").is_file():
            out.append(p.relative_to(arch).as_posix())
    return out


def read_info(archive_dir, rel):
    return json.loads((Path(archive_dir) / rel / "info.json").read_text(encoding="utf-8"))


class ContentHashTests(unittest.TestCase):
    def test_hash_is_sha256_of_content(self):
        import hashlib
        with tempfile.TemporaryDirectory() as td:
            p = write_media(Path(td) / "a.png", b"hello")
            self.assertEqual(assets_core.file_content_hash(p),
                             hashlib.sha256(b"hello").hexdigest())

    def test_identical_content_has_same_hash(self):
        with tempfile.TemporaryDirectory() as td:
            a = write_media(Path(td) / "a.png", b"same")
            b = write_media(Path(td) / "b.png", b"same")
            self.assertEqual(assets_core.file_content_hash(a),
                             assets_core.file_content_hash(b))

    def test_oversized_file_is_not_hashed(self):
        """超过上限返回 None → 退化成只按路径去重, 不读大文件。"""
        with tempfile.TemporaryDirectory() as td:
            p = write_media(Path(td) / "big.png", b"0123456789")
            self.assertIsNone(assets_core.file_content_hash(p, limit=4))

    def test_missing_file_returns_none(self):
        self.assertIsNone(assets_core.file_content_hash("/nonexistent/nope.png"))

    def test_lookup_does_not_create_index(self):
        state = {"a.png": {"size": 1, "mtime_ns": 1}}
        self.assertIsNone(assets_core._content_lookup(state, "deadbeef"))
        self.assertNotIn("__content__", state)


class MovedFileMergeTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        root = Path(self._td.name)
        self.out = root / "output"
        self.arch = root / "archive"
        self.out.mkdir()
        self.arch.mkdir()
        self.state = {}

    def tearDown(self):
        self._td.cleanup()

    def archive(self, rel):
        src = self.out / rel
        return assets_core.archive_file(rel, src, self.arch, self.state, CFG,
                                        source_root=self.out)

    def test_first_archive_creates_record_and_index(self):
        write_media(self.out / "角色A" / "图.png", b"payload")
        r = self.archive("角色A/图.png")
        self.assertIn("dir", r)
        self.assertEqual(len(run_dirs(self.arch)), 1)
        h = assets_core.file_content_hash(self.out / "角色A" / "图.png")
        self.assertEqual(self.state["__content__"][h], r["dir"])
        self.assertEqual(read_info(self.arch, r["dir"])["content_hash"], h)

    def test_rename_merges_into_existing_record(self):
        """改名(旧路径消失) → 复用原记录, 记录数不增。"""
        write_media(self.out / "角色A" / "图.png", b"payload")
        first = self.archive("角色A/图.png")
        os.replace(self.out / "角色A" / "图.png", self.out / "角色A" / "改名.png")

        second = self.archive("角色A/改名.png")
        self.assertTrue(second.get("merged"))
        self.assertEqual(second["dir"], first["dir"])
        self.assertEqual(len(run_dirs(self.arch)), 1)
        info = read_info(self.arch, first["dir"])
        self.assertEqual(info["source_rel"], "角色A/改名.png")
        self.assertIn("moved_at", info)

    def test_move_to_other_folder_updates_folder_field(self):
        write_media(self.out / "角色A" / "图.png", b"payload")
        first = self.archive("角色A/图.png")
        (self.out / "角色B").mkdir()
        os.replace(self.out / "角色A" / "图.png", self.out / "角色B" / "图.png")

        second = self.archive("角色B/图.png")
        self.assertTrue(second.get("merged"))
        self.assertEqual(read_info(self.arch, first["dir"])["folder"], "角色B")

    def test_merge_removes_stale_state_key(self):
        write_media(self.out / "a.png", b"payload")
        self.archive("a.png")
        os.replace(self.out / "a.png", self.out / "b.png")
        self.archive("b.png")
        self.assertNotIn("a.png", self.state)
        self.assertIn("b.png", self.state)

    def test_merge_keeps_category(self):
        write_media(self.out / "a.png", b"payload")
        first = self.archive("a.png")
        cid = assets_core.create_category(self.arch, "我的分类")["category"]["id"]
        assets_core.assign_category(self.arch, [first["dir"]], cid)

        os.replace(self.out / "a.png", self.out / "b.png")
        self.archive("b.png")
        self.assertEqual(read_info(self.arch, first["dir"])["category"], cid)

    def test_copy_keeps_two_records(self):
        """两份都在 → 用户真的存了两份, 保持独立记录。"""
        write_media(self.out / "a.png", b"payload")
        self.archive("a.png")
        shutil.copy2(self.out / "a.png", self.out / "b.png")

        second = self.archive("b.png")
        self.assertFalse(second.get("merged"))
        self.assertEqual(len(run_dirs(self.arch)), 2)

    def test_merge_skipped_when_record_dir_missing(self):
        """索引指向的记录目录没了 → 老老实实新建一份。"""
        write_media(self.out / "a.png", b"payload")
        first = self.archive("a.png")
        h = assets_core.file_content_hash(self.out / "a.png")
        shutil.rmtree(self.arch / first["dir"])
        self.state["__content__"][h] = first["dir"]

        os.replace(self.out / "a.png", self.out / "b.png")
        second = self.archive("b.png")
        self.assertFalse(second.get("merged"))
        self.assertEqual(len(run_dirs(self.arch)), 1)

    def test_merge_skipped_when_info_unreadable(self):
        write_media(self.out / "a.png", b"payload")
        first = self.archive("a.png")
        (self.arch / first["dir"] / "info.json").write_text("{broken", encoding="utf-8")

        os.replace(self.out / "a.png", self.out / "b.png")
        second = self.archive("b.png")
        self.assertFalse(second.get("merged"))
        self.assertEqual(len(run_dirs(self.arch)), 2)

    def test_different_content_is_not_merged(self):
        write_media(self.out / "a.png", b"payload-one")
        self.archive("a.png")
        write_media(self.out / "b.png", b"payload-two")
        second = self.archive("b.png")
        self.assertFalse(second.get("merged"))
        self.assertEqual(len(run_dirs(self.arch)), 2)

    def test_changed_file_at_same_path_still_archives_new_version(self):
        """同一路径内容变了 → 照旧归档新版本, 不能被合并逻辑吞掉。"""
        write_media(self.out / "a.png", b"v1")
        self.archive("a.png")
        write_media(self.out / "a.png", b"v2-different-length")
        second = self.archive("a.png")
        self.assertFalse(second.get("merged"))
        self.assertEqual(len(run_dirs(self.arch)), 2)


class DeleteRunIndexTests(unittest.TestCase):
    def test_delete_run_drops_index_entry(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out, arch = root / "output", root / "archive"
            out.mkdir()
            arch.mkdir()
            write_media(out / "a.png", b"payload")
            state = {}
            r = assets_core.archive_file("a.png", out / "a.png", arch, state, CFG,
                                         source_root=out)
            h = assets_core.file_content_hash(out / "a.png")
            self.assertIn(h, state["__content__"])

            assets_core.delete_run(arch, out, state, r["dir"])
            self.assertNotIn(h, state.get("__content__", {}))

            # 索引清掉后, 同内容的新文件应当正常新建记录, 不会指向已删目录
            write_media(out / "b.png", b"payload")
            again = assets_core.archive_file("b.png", out / "b.png", arch, state, CFG,
                                             source_root=out)
            self.assertFalse(again.get("merged"))
            self.assertEqual(len(run_dirs(arch)), 1)


class ScanMovedFileTests(unittest.TestCase):
    """走完整 scan_all: 整理 output 后扫描, 记录数必须不涨。"""

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

    def scan(self):
        return assets_core.scan_all(self.out, self.arch, self.state, CFG)

    def test_scan_after_move_keeps_record_count(self):
        write_media(self.out / "角色A" / "图.png", b"payload")
        self.assertEqual(self.scan(), 1)
        self.assertEqual(len(run_dirs(self.arch)), 1)

        (self.out / "角色B").mkdir()
        os.replace(self.out / "角色A" / "图.png", self.out / "角色B" / "图.png")
        self.assertEqual(self.scan(), 0)          # 不算新增
        self.assertEqual(len(run_dirs(self.arch)), 1)
        info = read_info(self.arch, run_dirs(self.arch)[0])
        self.assertEqual(info["source_rel"], "角色B/图.png")

    def test_scan_reports_copy_as_new(self):
        write_media(self.out / "a.png", b"payload")
        self.scan()
        shutil.copy2(self.out / "a.png", self.out / "b.png")
        self.assertEqual(self.scan(), 1)
        self.assertEqual(len(run_dirs(self.arch)), 2)

    def test_state_persisted_after_merge(self):
        write_media(self.out / "a.png", b"payload")
        self.scan()
        os.replace(self.out / "a.png", self.out / "b.png")
        self.scan()
        saved = json.loads((self.arch / "archive_state.json").read_text(encoding="utf-8"))
        self.assertIn("b.png", saved)
        self.assertNotIn("a.png", saved)
        self.assertIn("__content__", saved)


if __name__ == "__main__":
    unittest.main()
