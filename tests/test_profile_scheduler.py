"""OBS-27: scheduler counters survive mid-capture USM retirement."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

BINARY = Path(sys.argv.pop(1)).resolve()


class SchedulerTests(unittest.TestCase):
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
