import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import assets_core


class AudioAssetSupportTests(unittest.TestCase):
    def test_audio_extensions_are_scanned(self):
        expected = {
            ".wav", ".mp3", ".flac", ".ogg", ".opus",
            ".m4a", ".aac", ".aiff", ".aif", ".wma",
        }
        self.assertTrue(expected.issubset(assets_core.AUDIO_EXT))
        self.assertTrue(expected.issubset(assets_core.ALL_EXT))

    def test_music_workflow_text_fields_are_extracted(self):
        graph = {
            "minimax": {"class_type": "MiniMaxMusic3TextEncode", "inputs": {
                "caption": "gentle piano and warm strings",
                "lyrics": "The morning lights the quiet street",
            }},
            "yue2": {"class_type": "YuE2GenerateMusic", "inputs": {
                "style": "dream pop, soft female vocal",
                "lyrics": "We follow where the blue waves go",
                "abc": "",
            }},
        }

        parsed = assets_core.parse_prompt_graph(graph)

        self.assertIn("gentle piano and warm strings", parsed["positive"])
        self.assertIn("The morning lights the quiet street", parsed["positive"])
        self.assertIn("dream pop, soft female vocal", parsed["positive"])
        self.assertIn("We follow where the blue waves go", parsed["positive"])
        self.assertEqual(len(parsed["texts"]), 4)

    @patch.object(assets_core, "extract_audio_metadata", return_value=(None, None, 12.5))
    def test_scan_archives_and_indexes_audio(self, _extract_audio_metadata):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "output"
            archive_dir = root / "archive"
            output_dir.mkdir()
            audio_file = output_dir / "song.WAV"
            audio_file.write_bytes(b"test audio data")

            state = {"__baseline_done__": True}
            count = assets_core.scan_all(
                output_dir,
                archive_dir,
                state,
                {"archive_existing": False, "thumb_width": 480},
            )

            self.assertEqual(count, 1)
            runs = assets_core.list_runs(archive_dir)
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0]["kind"], "audio")
            self.assertEqual(runs[0]["media"], "song.WAV")
            self.assertEqual(runs[0]["media_duration"], 12.5)

            archived_dir = archive_dir / runs[0]["dir"]
            self.assertEqual((archived_dir / "song.WAV").read_bytes(), b"test audio data")
            self.assertFalse((archived_dir / "thumb.jpg").exists())
            info = json.loads((archived_dir / "info.json").read_text(encoding="utf-8"))
            self.assertEqual(info["kind"], "audio")
            self.assertEqual(info["media_duration"], 12.5)

    def test_media_path_only_serves_manifest_assets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir) / "archive"
            run_dir = archive / "2026-11-05" / "run-1"
            run_dir.mkdir(parents=True)
            (run_dir / "audio.wav").write_bytes(b"audio")
            (run_dir / "secret.txt").write_text("private", encoding="utf-8")
            (archive / "archive_state.json").write_text("{}", encoding="utf-8")
            info = {
                "media": "audio.wav",
                "thumb": None,
                "has_workflow": False,
            }
            (run_dir / "info.json").write_text(json.dumps(info), encoding="utf-8")

            self.assertEqual(
                assets_core.safe_media_path(archive, "2026-11-05/run-1/audio.wav"),
                (run_dir / "audio.wav").resolve(),
            )
            self.assertIsNone(assets_core.safe_media_path(archive, "2026-11-05/run-1/secret.txt"))
            self.assertIsNone(assets_core.safe_media_path(archive, "archive_state.json"))
            self.assertIsNone(assets_core.safe_media_path(archive, "2026-11-05/run-1/info.json"))
            self.assertIsNone(assets_core.safe_media_path(archive, "2026-11-05/run-1/workflow.json"))
            self.assertIsNone(assets_core.safe_media_path(
                archive, "2026-11-05/run-1/audio.wav", workflow_only=True
            ))

            info["has_workflow"] = True
            (run_dir / "workflow.json").write_text("{}", encoding="utf-8")
            (run_dir / "info.json").write_text(json.dumps(info), encoding="utf-8")
            self.assertEqual(
                assets_core.safe_media_path(
                    archive, "2026-11-05/run-1/workflow.json", workflow_only=True
                ),
                (run_dir / "workflow.json").resolve(),
            )

    def test_output_and_archive_overlap_is_not_scanned(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            shared = Path(temp_dir) / "shared"
            shared.mkdir()
            (shared / "song.wav").write_bytes(b"audio")
            state = {"__baseline_done__": True}

            count = assets_core.scan_all(
                shared,
                shared / "archive",
                state,
                {"archive_existing": False, "thumb_width": 480},
            )

            self.assertEqual(count, 0)
            self.assertFalse((shared / "archive").exists())

    @patch.object(assets_core, "extract_audio_metadata", return_value=(None, None, 8.0))
    def test_scan_skips_symlink_files(self, _extract_audio_metadata):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "output"
            output_dir.mkdir()
            outside = root / "outside.wav"
            outside.write_bytes(b"audio")
            link = output_dir / "linked.wav"
            try:
                link.symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")

            archive = root / "archive"
            count = assets_core.scan_all(
                output_dir,
                archive,
                {"__baseline_done__": True},
                {"archive_existing": False, "thumb_width": 480},
            )

            self.assertEqual(count, 0)
            self.assertEqual(assets_core.list_runs(archive), [])

    def test_scan_tolerates_missing_archive_dir(self):
        """归档目录还不存在(首次扫描/被用户删掉)时, 只记基线也要能把状态落盘。

        此前 save_state 直接往 archive_dir 里写, 目录不存在就抛
        FileNotFoundError, 把整轮扫描带崩。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "output"
            output_dir.mkdir()
            (output_dir / "song.wav").write_bytes(b"audio")
            archive = root / "archive"

            count = assets_core.scan_all(
                output_dir,
                archive,
                {},
                {"archive_existing": False, "thumb_width": 480},
            )

            self.assertEqual(count, 0)
            self.assertTrue(archive.is_dir())
            self.assertIn("song.wav", assets_core.load_state(archive))

    def test_backup_skips_symlinks_when_supported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive = root / "archive"
            backup = root / "backups"
            archive.mkdir()
            base_dir = root / "custom_nodes" / "ComfyUI-AssetManager"
            base_dir.mkdir(parents=True)
            external = root / "outside.txt"
            external.write_text("must not be included", encoding="utf-8")
            try:
                (archive / "linked.txt").symlink_to(external)
            except OSError as exc:
                self.skipTest(f"symlink creation is unavailable: {exc}")

            result = assets_core.backup_assets(
                {"archive_dir": str(archive), "backup_dir": str(backup)},
                base_dir,
            )

            self.assertTrue(result["ok"])
            with zipfile.ZipFile(result["file"]) as zf:
                self.assertNotIn("assets/linked.txt", zf.namelist())

    def test_backup_rejects_overlapping_roots_and_uses_unique_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            archive = root / "archive"
            backup = root / "backups"
            archive.mkdir()
            (archive / "asset.txt").write_text("asset", encoding="utf-8")
            base_dir = root / "custom_nodes" / "ComfyUI-AssetManager"
            base_dir.mkdir(parents=True)

            overlap_result = assets_core.backup_assets(
                {"archive_dir": str(archive), "backup_dir": str(archive / "backups")},
                base_dir,
            )
            self.assertFalse(overlap_result["ok"])

            cfg = {"archive_dir": str(archive), "backup_dir": str(backup)}
            first = assets_core.backup_assets(cfg, base_dir)
            second = assets_core.backup_assets(cfg, base_dir)
            self.assertTrue(first["ok"])
            self.assertTrue(second["ok"])
            self.assertNotEqual(first["name"], second["name"])
            with zipfile.ZipFile(first["file"]) as zf:
                self.assertIn("assets/asset.txt", zf.namelist())

    @patch.object(assets_core, "extract_audio_metadata", return_value=(None, None, None))
    def test_audio_prompt_can_be_recovered_from_history(self, _extract_audio_metadata):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "output" / "music.wav"
            source.parent.mkdir()
            source.write_bytes(b"audio")
            archive_dir = root / "archive"
            graph = {
                "1": {
                    "class_type": "TextEncode",
                    "_meta": {"title": "Audio prompt"},
                    "inputs": {"text": "warm piano with soft strings"},
                }
            }
            workflow = {"nodes": []}

            result = assets_core.archive_file(
                "music.wav",
                source,
                archive_dir,
                {},
                {"thumb_width": 480},
                prompt_resolver=lambda _rel, _src: (graph, workflow),
            )

            self.assertEqual(result["kind"], "audio")
            run = assets_core.list_runs(archive_dir)[0]
            self.assertEqual(run["positive"], "warm piano with soft strings")
            self.assertEqual(run["prompt_source"], "history")
            self.assertTrue(run["has_workflow"])
            self.assertTrue((archive_dir / result["dir"] / "workflow.json").is_file())


if __name__ == "__main__":
    unittest.main()
