"""OBS-27: scheduler counters survive mid-capture USM retirement."""
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

BINARY = Path(sys.argv.pop(1)).resolve()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import bench_perf15 as bench
import perf15_evidence as evidence


class SchedulerTests(unittest.TestCase):
    def test_rev30_current_profiler_passes_evidence_validation(self):
        cases = ((0, 0, 'fixed'), (1, 0, None),
                 (1, 1, 'sharpness-bypass'), (1, 0, 'disabled'))
        for adaptive, threshold, outcome in cases:
            with self.subTest(adaptive=adaptive, threshold=threshold, outcome=outcome):
                self.validate_capture(adaptive, threshold, outcome)

    def validate_capture(self, adaptive, threshold, outcome):
        env = {key: value for key, value in os.environ.items() if not key.startswith('UP_PROFILE_')}
        env.update(UP_PROFILE_WARMUP='0', UP_PROFILE_ADAPTIVE=str(adaptive),
                   UP_PROFILE_SHARP_THRESHOLD=str(threshold))
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'trace.csv'
            command = [str(BINARY), '1', '2', '64', '64', '2700', '0', '0', '0', '0', str(path)]
            process = self.run_profiler(command, env, outcome == 'disabled')
            result = json.loads(process.stdout)
            if outcome is not None:
                self.assertEqual(result['adaptive_outcome'], outcome)
            record = dict(job=dict(adaptive=adaptive), result=result,
                          summary=bench.trace_summary(path, adaptive))
            metrics = evidence.verify_trace(record, path)
            for name, value in metrics.items():
                self.assertAlmostEqual(value, result[name], delta=.001)

    def run_profiler(self, command, env, single_cpu):
        affinity = os.sched_getaffinity(0)
        try:
            if single_cpu:
                os.sched_setaffinity(0, {min(affinity)})
            return subprocess.run(command, env=env, capture_output=True, text=True,
                                  timeout=30, check=True)
        finally:
            os.sched_setaffinity(0, affinity)

    def test_rev28_trace_marks_sharpness_bypass_inactive(self):
        env = {key: value for key, value in os.environ.items() if not key.startswith('UP_PROFILE_')}
        env.update(UP_PROFILE_WARMUP='0', UP_PROFILE_SHARP_THRESHOLD='3500',
                   UP_PROFILE_ADAPTIVE='1')
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / 'trace.csv'
            result = subprocess.run([str(BINARY), '1', '8', '128', '128', '70',
                                     '0', '0', '0', '0', str(trace)], env=env,
                                    capture_output=True, text=True, timeout=20, check=True)
            with trace.open() as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual(json.loads(result.stdout)['adaptive_outcome'], 'sharpness-bypass')
        self.assertEqual([row.get('adaptive_active') for row in rows], ['1'] * 59 + ['0'] * 11)

    def capture(self, workers, threshold, warmup=1):
        env = {key: value for key, value in os.environ.items() if not key.startswith('UP_PROFILE_')}
        env.update(UP_PROFILE_WARMUP=str(warmup), UP_PROFILE_SHARP_THRESHOLD=str(threshold))
        process = subprocess.run([str(BINARY), '1', str(workers), '64', '64', '64',
                                  '0', '1', '0', '0'], env=env, capture_output=True,
                                 text=True, timeout=20, check=True)
        return json.loads(process.stdout)

    def check_counters(self, row):
        for key in ('u_runtime_ns', 'u_runqueue_ns', 'u_slices'):
            self.assertGreaterEqual(row[key], 0)
            self.assertLess(row[key], 40_000_000_000)

    def test_obs27_retired_workers_keep_measured_counters(self):
        row = self.capture(2, 1)
        self.assertEqual(row['skip_usm'], 1)
        self.assertEqual(row['usm_effective'], 0)
        self.check_counters(row)
        self.assertGreater(row['u_runtime_ns'], 0)
        self.assertGreater(row['u_slices'], 0)

    def test_obs27_disabled_or_already_retired_usm_reports_zero(self):
        for workers, threshold, warmup in ((0, 0, 1), (2, 1, 60)):
            with self.subTest(workers=workers, warmup=warmup):
                row = self.capture(workers, threshold, warmup)
                self.assertEqual(row['usm_effective'], 0)
                for key in ('u_runtime_ns', 'u_runqueue_ns', 'u_slices'):
                    self.assertEqual(row[key], 0)

    def test_obs27_uninterrupted_usm_reports_measured_counters(self):
        row = self.capture(2, 0)
        self.assertEqual(row['skip_usm'], 0)
        self.assertEqual(row['usm_effective'], 2)
        self.check_counters(row)
        self.assertGreater(row['u_runtime_ns'], 0)
        self.assertGreater(row['u_slices'], 0)


if __name__ == '__main__':
    unittest.main()
