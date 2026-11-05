"""分类功能测试: 文件夹自动派生、我的分类增删改、归档记录改分类。"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import assets_core


def make_run(archive_dir, run_id, source_rel="角色A/图.png", extra=None):
    """在归档目录里造一条最小可用的归档记录。"""
    run_dir = Path(archive_dir) / run_id
    run_dir.mkdir(parents=True)
    info = {
        "run_id": run_dir.name,
        "archived_at": "2026-11-05T18:00:00",
        "generated_at": "2026-11-05T17:59:00",
        "source_rel": source_rel,
        "media": Path(source_rel).name,
        "kind": "image",
    }
    if extra:
        info.update(extra)
    (run_dir / "info.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    (run_dir / info["media"]).write_bytes(b"x")
    return run_dir


class FolderDerivationTests(unittest.TestCase):
    def test_explicit_folder_wins(self):
        info = {"folder": "场景/夜景", "source_rel": "角色A/图.png"}
        self.assertEqual(assets_core.resolve_folder(info), "场景/夜景")

    def test_folder_derived_from_source_rel(self):
        info = {"source_rel": "角色A/图.png"}
        self.assertEqual(assets_core.resolve_folder(info), "角色A")

    def test_root_files_have_empty_folder(self):
        self.assertEqual(assets_core.resolve_folder({"source_rel": "图.png"}), "")
        self.assertEqual(assets_core.resolve_folder({}), "")

    def test_backslashes_are_normalised(self):
        info = {"source_rel": "角色A\\场景\\图.png"}
        self.assertEqual(assets_core.resolve_folder(info), "角色A/场景")


class CategoryStoreTests(unittest.TestCase):
    def test_create_list_and_duplicate_guard(self):
        with tempfile.TemporaryDirectory() as td:
            first = assets_core.create_category(td, "场景概念")
            self.assertTrue(first["ok"])
            self.assertEqual(first["category"]["name"], "场景概念")

            dup = assets_core.create_category(td, " 场景概念 ")
            self.assertFalse(dup["ok"])
            self.assertIn("exists", dup["error"])

            names = [c["name"] for c in assets_core.load_categories(td)["categories"]]
            self.assertEqual(names, ["场景概念"])

    def test_empty_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertFalse(assets_core.create_category(td, "   ")["ok"])

    def test_rename_and_delete(self):
        with tempfile.TemporaryDirectory() as td:
            cid = assets_core.create_category(td, "待整理")["category"]["id"]
            renamed = assets_core.rename_category(td, cid, "已整理")
            self.assertTrue(renamed["ok"])
            self.assertEqual(renamed["categories"][0]["name"], "已整理")

            deleted = assets_core.delete_category(td, cid)
            self.assertTrue(deleted["ok"])
            self.assertEqual(assets_core.load_categories(td)["categories"], [])
            self.assertFalse(assets_core.delete_category(td, cid)["ok"])

    def test_rename_to_existing_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            a = assets_core.create_category(td, "场景")["category"]["id"]
            b = assets_core.create_category(td, "角色")["category"]["id"]
            clash = assets_core.rename_category(td, b, "场景")
            self.assertFalse(clash["ok"])
            self.assertIn("exists", clash["error"])
            # 改回自己的名字(仅大小写/空格不同)不应被拦
            self.assertTrue(assets_core.rename_category(td, a, " 场景 ")["ok"])

    def test_name_is_sanitised_and_capped(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertFalse(assets_core.create_category(td, "\x00\x01\n\t")["ok"])
            long_name = assets_core.create_category(td, "长" * 200)["category"]["name"]
            self.assertEqual(len(long_name), assets_core.CATEGORY_NAME_MAX)

    def test_corrupt_file_does_not_raise(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "categories.json").write_text("{not json", encoding="utf-8")
            self.assertEqual(assets_core.load_categories(td)["categories"], [])


class AssignCategoryTests(unittest.TestCase):
    def test_assign_and_clear(self):
        with tempfile.TemporaryDirectory() as td:
            make_run(td, "2026-11-05/run-1")
            cid = assets_core.create_category(td, "场景概念")["category"]["id"]

            result = assets_core.assign_category(td, ["2026-11-05/run-1"], cid)
            self.assertTrue(result["ok"])
            self.assertEqual(result["updated"], ["2026-11-05/run-1"])

            runs = assets_core.list_runs(td)
            self.assertEqual(runs[0]["category"], cid)
            self.assertEqual(runs[0]["folder"], "角色A")

            cleared = assets_core.assign_category(td, ["2026-11-05/run-1"], None)
            self.assertTrue(cleared["ok"])
            self.assertIsNone(assets_core.list_runs(td)[0]["category"])

    def test_unknown_category_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            make_run(td, "2026-11-05/run-1")
            result = assets_core.assign_category(td, ["2026-11-05/run-1"], "nope")
            self.assertFalse(result["ok"])

    def test_path_traversal_is_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            make_run(td, "2026-11-05/run-1")
            cid = assets_core.create_category(td, "场景概念")["category"]["id"]
            outside = Path(td).parent / "outside-run"
            result = assets_core.assign_category(td, ["../../outside-run"], cid)
            self.assertTrue(result["ok"])
            self.assertEqual(result["updated"], [])
            self.assertEqual(result["skipped"][0]["reason"], "invalid path")
            self.assertFalse(outside.exists())

    def test_list_dir_field_is_the_assign_contract(self):
        """前端传的是 list_runs 的 dir 字段, 二者必须对得上。"""
        with tempfile.TemporaryDirectory() as td:
            make_run(td, "2026-11-05/run-1")
            cid = assets_core.create_category(td, "场景概念")["category"]["id"]
            run = assets_core.list_runs(td)[0]
            self.assertEqual(run["dir"], "2026-11-05/run-1")
            result = assets_core.assign_category(td, [run["dir"]], cid)
            self.assertEqual(result["updated"], [run["dir"]])
            self.assertEqual(assets_core.list_runs(td)[0]["category"], cid)

    def test_bare_run_name_is_rejected(self):
        """只给目录名(不带日期层)不能命中, 避免同名歧义。"""
        with tempfile.TemporaryDirectory() as td:
            make_run(td, "2026-11-05/run-1")
            cid = assets_core.create_category(td, "场景概念")["category"]["id"]
            result = assets_core.assign_category(td, ["run-1"], cid)
            self.assertEqual(result["updated"], [])
            self.assertEqual(result["skipped"][0]["reason"], "invalid path")

    def test_symlinked_run_dir_is_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "real-run"
            make_run(td, "real-run")
            link_parent = Path(td) / "2026-11-05"
            link_parent.mkdir()
            link = link_parent / "run-link"
            try:
                os.symlink(target, link, target_is_directory=True)
            except (OSError, NotImplementedError, AttributeError):
                self.skipTest("symlink not permitted on this platform")
            cid = assets_core.create_category(td, "场景概念")["category"]["id"]
            result = assets_core.assign_category(td, ["2026-11-05/run-link"], cid)
            self.assertEqual(result["updated"], [])
            self.assertEqual(result["skipped"][0]["reason"], "invalid path")
            # 软链目标本身不能被改写
            info = json.loads((target / "info.json").read_text(encoding="utf-8"))
            self.assertNotIn("category", info)

    def test_missing_info_json_is_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "2026-11-05" / "empty-run"
            run_dir.mkdir(parents=True)
            cid = assets_core.create_category(td, "场景概念")["category"]["id"]
            result = assets_core.assign_category(td, ["2026-11-05/empty-run"], cid)
            self.assertEqual(result["updated"], [])
            self.assertEqual(result["skipped"][0]["reason"], "missing info.json")


if __name__ == "__main__":
    unittest.main()
