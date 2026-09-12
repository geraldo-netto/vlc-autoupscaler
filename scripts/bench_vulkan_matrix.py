#!/usr/bin/env python3
"""Run sequential direct-Vulkan controls; preserve commands, hashes and raw output."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def hashes(paths):
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def jobs():
    for device in (0, 1):
        for factor in (2, 4):
            for combined, variants in (
                (False, ("cpu", "naive", "separable", "lookup-direct")),
                (True, ("cpu", "separable", "lookup-direct", "lookup-fused-direct", "lookup-fused-resident")),
            ):
                yield from repeats(device, factor, combined, variants, 0, 1)
            paced = ("cpu", "lookup-direct")
            if device == 0:
                paced += ("lookup-fused-direct", "lookup-fused-resident")
            yield from repeats(device, factor, True, paced, 33333, 32)


def repeats(device, factor, combined, variants, period, sequence):
    for pair in range(3):
        order = variants if pair % 2 == 0 else tuple(reversed(variants))
        for variant in order:
            yield dict(device=device, factor=factor, combined=combined, variant=variant,
                       period=period, sequence=sequence, pair=pair)


def command(build, clip, job, timing=False):
    variant = job["variant"]
    backend = "cpu" if variant == "cpu" else "gpu"
    variant = "separable" if variant == "cpu" else variant
    shader = "vulkan_spline36.spv" if variant == "naive" else "vulkan_separable.spv"
    usm = str(build / "vulkan_usm.spv") if job["combined"] else "-"
    return [str(build / "bench_vulkan_scale"), str(build / shader), str(job["device"]),
            str(job["factor"]), backend, str(clip), variant, usm, str(int(timing)),
            str(job["period"]), "12", str(job["sequence"])]


def capture(build, clip, job, timing=False):
    cmd = command(build, clip, job, timing)
    load = os.getloadavg()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    row = dict(job=job, timing=timing, command=cmd, returncode=result.returncode,
               stdout=result.stdout, stderr=result.stderr, host_load_start=load,
               host_load_end=os.getloadavg())
    row["measurements"] = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
    print(job, result.returncode, row["measurements"][-1:], flush=True)
    return row


def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    paths = [args.build / "bench_vulkan_scale"] + sorted(args.build.glob("vulkan_*.spv"))
    paths += sorted(Path("tests").glob("*vulkan*"))
    paths += [Path(__file__), Path("scripts/compile_vulkan_shader.py"), args.clip]
    manifest = hashes(paths)
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    rows = []
    for job in jobs():
        row = capture(args.build, args.clip, job)
        rows.append(row)
        (args.output / "matrix.json").write_text(json.dumps(rows, indent=2) + "\n")
        if row["returncode"]:
            raise RuntimeError("benchmark failed; partial evidence retained")
    profiles(args, rows)
    if hashes(paths) != manifest:
        raise RuntimeError("inputs changed during measurement; reject this matrix")
    (args.output / "verified.json").write_text('{"hashes_unchanged": true}\n')


def profiles(args, rows):
    for device in (0, 1):
        for factor in (2, 4):
            for variant in ("naive", "lookup-direct", "lookup-fused-direct", "lookup-fused-resident"):
                job = dict(device=device, factor=factor, combined=variant != "naive",
                           variant=variant, period=0, sequence=1, pair=0)
                row = capture(args.build, args.clip, job, True)
                rows.append(row)
                (args.output / "matrix.json").write_text(json.dumps(rows, indent=2) + "\n")
                if row["returncode"]:
                    raise RuntimeError("stage timing failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    parser.add_argument("clip", type=Path, help="960x540 I420 with at least 32 decoded frames")
    parser.add_argument("output", type=Path, help="new evidence directory")
    run(parser.parse_args())
