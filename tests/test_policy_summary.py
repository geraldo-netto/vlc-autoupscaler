#!/usr/bin/env python3
"""OBS-20: inactive tuners must not be reported as exploring."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from bench_playback_policies import summarize_trace


class SummaryTests(unittest.TestCase):
    def test_fixed_pool_is_not_exploring(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.csv"
            path.write_text("frame,total,phase,workers,changed,skipped\n0,123,0,12,0,0\n")
            summary = summarize_trace(path)
        self.assertEqual(summary["exploration_frames"], 0)

    def test_active_search_excludes_settled_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.csv"
            path.write_text("frame,total,phase,workers,changed,skipped\n"
                            "0,123,0,12,0,0\n1,120,1,12,0,0\n"
                            "2,119,2,8,1,0\n3,118,3,8,0,0\n")
            summary = summarize_trace(path, adaptive=True)
        self.assertEqual(summary["exploration_frames"], 3)
        self.assertEqual(summary["incumbent_worker_counts"], [8, 12])
        self.assertEqual(summary["changed_frames"], [2])


if __name__ == "__main__":
    unittest.main()
