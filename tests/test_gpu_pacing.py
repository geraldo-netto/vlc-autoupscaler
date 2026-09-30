#!/usr/bin/env python3
"""Telemetry must describe measured frames, excluding startup and teardown."""
from pathlib import Path
import sys
import unittest
import hashlib
from io import BytesIO
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from bench_gpu_pacing import telemetry_summary
from bench_vulkan_matrix import hashes
import bench_vulkan_matrix as matrix
import vulkan_devices as devices_backend
import subprocess
from types import SimpleNamespace


class BoundedStream(BytesIO):
    def read(self, size=-1):
        if not 0 < size <= 1024 * 1024:
            raise AssertionError('REV-17: whole-file or unbounded read')
        return super().read(size)


class InputHashTests(unittest.TestCase):
    def test_rev17_streams_inputs_in_bounded_blocks(self):
        data = b'frame' * 500000
        path = Path('clip.yuv')
        with patch.object(Path, 'open', return_value=BoundedStream(data)), \
                patch.object(Path, 'read_bytes', side_effect=AssertionError('whole-file read')):
            self.assertEqual(hashes([path]), {str(path): hashlib.sha256(data).hexdigest()})


class DeviceSelectionTests(unittest.TestCase):
    def test_rev11_discovery_and_selection_boundaries(self):
        for indices in ([], [0], [0, 1]):
            result = subprocess.CompletedProcess([], 0, str(indices), '')
            with patch.object(subprocess, 'run', return_value=result):
                self.assertEqual(devices_backend.discover(Path('build')), indices)
        self.assertEqual(devices_backend.select([0, 1], [1]), [1])
        with self.assertRaisesRegex(RuntimeError, 'no compatible'):
            devices_backend.select([])
        for selected in ([-1], [16], [True], [0, 0], [2]):
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                devices_backend.select([0, 1], selected)

    def test_rev11_zero_one_two_devices(self):
        for devices in ([], [0], [0, 1], [1, 3]):
            with self.subTest(devices=devices):
                jobs = list(matrix.jobs(devices))
                self.assertEqual({job['device'] for job in jobs}, set(devices))
                args = SimpleNamespace(devices=devices, build=Path('build'), clip=Path('clip'),
                                       output=Path('unused'))
                with patch.object(matrix, 'capture', return_value={'returncode': 0}) as capture, \
                        patch.object(Path, 'write_text'):
                    matrix.profiles(args, [])
                selected = {call.args[2]['device'] for call in capture.call_args_list}
                self.assertEqual(selected, set(devices))


class TelemetryTests(unittest.TestCase):
    def test_measurement_interval(self):
        samples = [dict(time_us=0, clock_hz=999), dict(time_us=100, clock_hz=200),
                   dict(time_us=200, clock_hz=400), dict(time_us=300, clock_hz=999)]
        bounds = [dict(measurement_start_us=100, measurement_end_us=200)]
        result = telemetry_summary(samples, bounds)
        self.assertEqual(result["samples"], 2)
        self.assertEqual(result["clock_hz"], dict(minimum=200, median=300, maximum=400))

    def test_uninstrumented_control(self):
        bounds = [dict(measurement_start_us=100, measurement_end_us=200)]
        self.assertEqual(telemetry_summary([], bounds)["samples"], 0)

    def test_sensor_errors_are_not_zero_measurements(self):
        samples = [dict(time_us=100, clock_hz="unavailable")]
        bounds = [dict(measurement_start_us=100, measurement_end_us=200)]
        self.assertNotIn("clock_hz", telemetry_summary(samples, bounds))


if __name__ == "__main__":
    unittest.main()
