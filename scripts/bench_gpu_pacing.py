#!/usr/bin/env python3
"""Read AMD GPU telemetry during sequential Vulkan cadence controls; never write sysfs."""
import argparse
import json
import os
from pathlib import Path
import random
import statistics
import subprocess
import time

from bench_playback_policies import digest
from bench_vulkan_matrix import command


def sensor_paths(device):
    hwmon = next((device / "hwmon").glob("hwmon*"))
    return dict(clock_hz=hwmon / "freq1_input", memory_hz=hwmon / "freq2_input",
                power_uw=hwmon / "power1_average", temperature_mc=hwmon / "temp1_input",
                busy_percent=device / "gpu_busy_percent")


def read_sensors(paths):
    values = {}
    for name, path in paths.items():
        try:
            values[name] = int(path.read_text())
        except (OSError, ValueError) as error:
            values[name] = str(error)
    return dict(time_us=time.monotonic_ns() / 1000, **values)


def jobs():
    rows = [dict(device=0, factor=2, combined=True, variant=variant,
                 period=period, sequence=1, telemetry=telemetry, timing=0)
            for variant in ("lookup-direct", "lookup-fused-direct")
            for period in (0, 8333, 16667, 33333, 41667) for telemetry in (0, 1)]
    rows.extend(dict(device=0, factor=2, combined=True, variant=variant,
                     period=period, sequence=1, telemetry=1, timing=1)
                for variant in ("lookup-direct", "lookup-fused-direct")
                for period in (0, 33333))
    return rows


def collect(cmd, paths, log, enabled):
    samples = []
    with log.open("w") as stream:
        child = subprocess.Popen(cmd, stdout=stream, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 90
            while child.poll() is None:
                if time.monotonic() > deadline:
                    raise TimeoutError("GPU benchmark timed out")
                if enabled:
                    samples.append(read_sensors(paths))
                time.sleep(.01)
            _, errors = child.communicate(timeout=5)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
    return child.returncode, errors, samples


def sensor_statistics(active):
    result = {}
    for name in active[0]:
        values = [row[name] for row in active if isinstance(row[name], (int, float))]
        if name != "time_us" and values:
            result[name] = dict(minimum=min(values), median=statistics.median(values), maximum=max(values))
    return result


def telemetry_summary(samples, measurements):
    bounds = next(row for row in measurements if "measurement_start_us" in row)
    active = [row for row in samples
              if bounds["measurement_start_us"] <= row["time_us"] <= bounds["measurement_end_us"]]
    result = dict(samples=len(active), bounds=bounds)
    if active:
        result.update(sensor_statistics(active))
    return result


def capture(args, job, repeat, index):
    cmd = command(args.build, args.clip, job, bool(job["timing"]))
    log = args.output / (str(index) + ".log")
    rc, errors, samples = collect(cmd, sensor_paths(args.device), log, job["telemetry"])
    measurements = [json.loads(line) for line in log.read_text().splitlines() if line.startswith("{")]
    row = dict(job=job, repeat=repeat, command=cmd, returncode=rc, stderr=errors,
               measurements=measurements, telemetry=samples, load=os.getloadavg())
    if not rc:
        row["telemetry_summary"] = telemetry_summary(samples, measurements)
    return row


def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    paths = [args.build / "bench_vulkan_scale", Path(__file__), args.clip,
             Path("scripts/bench_playback_policies.py"), Path("scripts/bench_vulkan_matrix.py")]
    paths += sorted(args.build.glob("vulkan_*.spv"))
    paths += sorted(Path("tests").glob("*vulkan*"))
    manifest = {str(path): digest(path) for path in paths}
    policy = (args.device / "power_dpm_force_performance_level").read_text()
    manifest["power_policy"] = policy
    manifest["sysfs_device"] = str(args.device.resolve())
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    randomizer = random.Random(20260914)
    rows = []
    for repeat in range(3):
        cases = jobs()
        randomizer.shuffle(cases)
        for job in cases:
            row = capture(args, job, repeat, len(rows))
            rows.append(row)
            (args.output / "results.json").write_text(json.dumps(rows, indent=2) + "\n")
            print(len(rows), job, row["returncode"], flush=True)
            if row["returncode"]:
                raise RuntimeError("benchmark failed; partial evidence retained")
    after = {str(path): digest(path) for path in paths}
    after["power_policy"] = (args.device / "power_dpm_force_performance_level").read_text()
    after["sysfs_device"] = str(args.device.resolve())
    if after != manifest:
        raise RuntimeError("inputs or power policy changed; reject these results")
    (args.output / "verified.json").write_text('{"hashes_and_policy_unchanged": true}\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    parser.add_argument("clip", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--device", type=Path, default=Path("/sys/class/drm/card1/device"))
    run(parser.parse_args())


if __name__ == "__main__":
    main()
