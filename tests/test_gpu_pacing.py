#!/usr/bin/env python3
"""Telemetry must describe measured frames, excluding startup and teardown."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from bench_gpu_pacing import telemetry_summary


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
