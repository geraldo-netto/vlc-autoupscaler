#!/usr/bin/env python3
"""PERF-15: uncertainty and guard failures must prevent policy promotion."""
from pathlib import Path
import json
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from bench_perf15 import CLIPS, METRICS, TREATMENTS, decisions, paired_plan
import bench_perf15


def pairs():
    rows = []
    for job in paired_plan():
        value = 1.01 if job["treatment"] == "duplicate" else .8
        rows.append(dict(**job, valid_outcomes=True, ratios={key: value for key in METRICS}))
    return rows


class DecisionTests(unittest.TestCase):
    def test_balanced_plan(self):
        rows = paired_plan()
        for clip in CLIPS:
            for treatment in TREATMENTS:
                subset = [row for row in rows if row["clip"] == clip and row["treatment"] == treatment]
                self.assertEqual({row["repeat"] for row in subset}, {0, 1, 2})
                self.assertTrue(all(set(row["order"]) == {"baseline", treatment} for row in subset))

    def test_repeatable_gain_can_pass(self):
        self.assertTrue(all(row["promote"] for row in decisions(pairs())["decisions"]))

    def test_guard_or_fallback_rejects(self):
        for key in METRICS:
            rows = pairs()
            row = next(row for row in rows if row["treatment"] == "latency")
            row["ratios"][key] = 1.051
            self.assertFalse(decisions(rows)["decisions"][-1]["promote"])
        rows = pairs()
        next(row for row in rows if row["treatment"] == "latency")["valid_outcomes"] = False
        self.assertFalse(decisions(rows)["decisions"][-1]["promote"])

    def test_noise_and_incomplete_repeats_reject(self):
        rows = pairs()
        for row in rows:
            if row["treatment"] == "duplicate":
                row["ratios"]["frame_p99"] = 1.3
        self.assertFalse(any(row["promote"] for row in decisions(rows)["decisions"]))
        rows = [row for row in pairs() if row["treatment"] == "duplicate" or row["repeat"] == 0]
        self.assertFalse(any(row["promote"] for row in decisions(rows)["decisions"]))

    def test_obs21_skip_identifies_earlier_pair_and_outcome(self):
        for valid, ratio in ((True, 1.051), (False, 1.0)):
            with self.subTest(valid=valid, ratio=ratio):
                self.check_skip_reason(valid, ratio)

    def check_skip_reason(self, valid, ratio):
        jobs = [dict(clip=clip, treatment="latency", repeat=1,
                     order=["baseline", "latency"]) for clip in CLIPS[:2]]
        failure = dict(valid_outcomes=valid, ratios={key: ratio for key in METRICS})
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(bench_perf15, "paired_plan", return_value=jobs), \
                patch.object(bench_perf15, "pair", return_value=failure) as capture, \
                patch.object(bench_perf15, "decisions", return_value={}):
            output = Path(directory)
            bench_perf15.compare(SimpleNamespace(output=output))
            skipped = json.loads((output/"skipped.json").read_text())
            capture.assert_called_once()
            self.assertEqual(len(skipped), 1)
            self.assertEqual(skipped[0]["repeat"], 1)
            self.assertEqual(skipped[0]["reason"],
                             "guard or adaptive outcome failed in an earlier pair")


if __name__ == "__main__":
    unittest.main()
