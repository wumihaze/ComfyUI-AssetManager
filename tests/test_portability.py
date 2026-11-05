"""部署位置可移植性测试: 路径必须跟随实际盘符/安装位置, 坏路径不能拖垮插件。"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import assets_core


class DeployPathPortabilityTests(unittest.TestCase):
    def test_ensure_dir_creates_and_returns_usable_path(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "nested" / "archive"
            result = assets_core.ensure_dir(str(target), str(Path(td) / "fallback"))
            self.assertEqual(Path(result).resolve(), target.resolve())
            self.assertTrue(target.is_dir())

    def test_ensure_dir_falls_back_when_path_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            blocker = Path(td) / "blocker"
            blocker.write_text("not a directory", encoding="utf-8")
            fallback = Path(td) / "fallback"
            result = assets_core.ensure_dir(str(blocker / "sub"), str(fallback))
            self.assertEqual(Path(result).resolve(), fallback.resolve())
            self.assertTrue(fallback.is_dir())

    def test_ensure_dir_returns_empty_when_everything_fails(self):
        with tempfile.TemporaryDirectory() as td:
            blocker = Path(td) / "blocker"
            blocker.write_text("not a directory", encoding="utf-8")
            self.assertEqual(assets_core.ensure_dir(str(blocker / "a"), str(blocker / "b")), "")

    def test_default_asset_dirs_follow_plugin_location(self):
        """默认归档/备份目录由插件所在位置推导, 与具体盘符无关。"""
        with tempfile.TemporaryDirectory() as td:
            plugin_dir = Path(td) / "ComfyUI" / "custom_nodes" / "ComfyUI-AssetManager"
            plugin_dir.mkdir(parents=True)
            archive_dir, backup_dir = assets_core.default_asset_dirs(str(plugin_dir))
            # 期望值也要 resolve: default_asset_dirs 内部 resolve 过, 而 Windows 的
            # TEMP 可能带 8.3 短名(RUNNER~1), 长名和短名指向同一个目录但字符串不等。
            comfy_root = (Path(td) / "ComfyUI").resolve()
            self.assertEqual(Path(archive_dir), comfy_root / "asset_archive")
            self.assertEqual(Path(backup_dir), comfy_root / "asset_backups")
            self.assertNotIn(":", Path(archive_dir).name)

    def test_config_with_foreign_absolute_path_does_not_raise(self):
        """配置里残留其它机器/已移除盘符的绝对路径时, 读取本身不应抛异常。"""
        with tempfile.TemporaryDirectory() as td:
            cfg_file = Path(td) / "config.json"
            cfg_file.write_text(
                '{"archive_dir": "Z:\\\\gone\\\\archive", "backup_dir": "Z:\\\\gone\\\\backups",'
                ' "thumb_width": 99999, "interval_sec": "soon"}',
                encoding="utf-8",
            )
            cfg = assets_core.load_config(td)
            self.assertEqual(cfg["archive_dir"], "Z:\\gone\\archive")
            # 越界数值与错误类型被丢弃, 回落到默认值
            self.assertEqual(cfg["thumb_width"], assets_core.DEFAULT_CONFIG["thumb_width"])
            self.assertEqual(cfg["interval_sec"], assets_core.DEFAULT_CONFIG["interval_sec"])


if __name__ == "__main__":
    unittest.main()
