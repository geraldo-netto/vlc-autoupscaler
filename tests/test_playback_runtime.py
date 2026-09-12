#!/usr/bin/env python3
"""BUILD-42: playback evidence must identify one exact plugin binary."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "playback_runtime", Path(__file__).resolve().parents[1] / "scripts/playback_runtime.py")
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)


class PlaybackRuntimeTests(unittest.TestCase):
    def test_maps_reject_duplicates_and_deleted_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "new/libautoupscale_plugin.so"
            old = root / "old/libautoupscale_plugin.so"
            line = f"100-200 r-xp 0000 00:00 1 {expected}\n"
            self.assertEqual(RUNTIME.verify_plugin_maps(line * 3, expected), expected)
            with self.assertRaises(ValueError):
                RUNTIME.verify_plugin_maps(line + f"200-300 r-xp 0 0 2 {old}\n", expected)
            with self.assertRaises(ValueError):
                RUNTIME.verify_plugin_maps(line.rstrip() + " (deleted)\n", expected)
            with self.assertRaises(ValueError):
                RUNTIME.verify_plugin_maps("", expected)

    def test_runtime_excludes_old_and_nested_plugins(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            system = root / "system"
            system.mkdir()
            (system / "libother_plugin.so").write_bytes(b"other")
            (system / "libautoupscale_plugin.so").write_bytes(b"old")
            plugin = root / "libautoupscale_plugin.so"
            plugin.write_bytes(b"new")
            core = root / "libvlccore.so.9"
            core.write_bytes(b"core")
            destination = root / "runtime"
            RUNTIME.prepare_runtime(destination, plugin, system, core)
            modules = list((destination / "vlc/plugins").rglob("*_plugin.so"))
            self.assertEqual(len(modules), 2)
            copies = [p for p in modules if p.name == plugin.name]
            self.assertEqual(copies[0].resolve(), plugin)
            self.assertFalse((destination / core.name).is_symlink())
            self.assertEqual((destination / core.name).read_bytes(), b"core")


if __name__ == "__main__":
    unittest.main()
