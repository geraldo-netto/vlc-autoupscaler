#!/usr/bin/env python3
"""OBS-20: inactive tuners must not be reported as exploring."""
import csv
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from bench_playback_policies import summarize_trace
from bench_perf15 import trace_summary


class SummaryTests(unittest.TestCase):
    def summaries(self, states, adaptive=True):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trace.csv'
            rows = [dict(dict(frame=i, total=123, workers=8, selected_workers=8,
                              changed=0, skipped=0), **state) for i, state in enumerate(states)]
            with path.open('w') as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            return summarize_trace(path, adaptive), trace_summary(path, adaptive)

    def test_rev28_bypass_excluded_before_and_after_settlement(self):
        for phase in ('0', '1', '2', '3'):
            for explicit in (False, True):
                states = [dict(phase=phase), dict(phase=phase), dict(phase=phase)]
                if explicit:
                    for i, state in enumerate(states):
                        state['adaptive_active'] = int(i == 0)
                with self.subTest(phase=phase, explicit=explicit):
                    for summary in self.bypass_summaries(states):
                        self.assertEqual(summary['exploration_frames'], int(phase != '3'))
                        self.assertEqual(summary['settled_frames'], int(phase == '3'))

    def bypass_summaries(self, states):
        rows = [dict(state, workers=8 if i == 0 else 0, skipped=int(i != 0))
                for i, state in enumerate(states)]
        return self.summaries(rows)

    def test_rev28_fixed_stopped_and_disabled_are_inactive(self):
        for phase in ('0', '1', '2', '3'):
            for active in ('0', '-1', '2', '', 'invalid'):
                for summary in self.summaries([dict(phase=phase, adaptive_active=active)]):
                    self.assertEqual(summary['exploration_frames'], 0)
                    self.assertEqual(summary['settled_frames'], 0)
            for summary in self.summaries([dict(phase=phase, adaptive_active='1')], False):
                self.assertEqual(summary['exploration_frames'], 0)
                self.assertEqual(summary['settled_frames'], 0)

    def test_rev28_only_active_transitions_restart(self):
        states = [dict(phase='3', adaptive_active='1'), dict(phase='0', adaptive_active='0'),
                  dict(phase='3', adaptive_active='1'), dict(phase='1', adaptive_active='1')]
        for summary in self.summaries(states):
            self.assertEqual(summary['restarts'], 1)
        for summary in self.summaries(states, False):
            self.assertEqual(summary['restarts'], 0)

    def test_rev28_nonpositive_workers_are_inactive(self):
        for workers in ('0', '-1', str(-(2**63))):
            states = [dict(phase='0', adaptive_active='1', workers=workers)]
            for summary in self.summaries(states):
                self.assertEqual(summary['exploration_frames'], 0)

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
