#!/usr/bin/env python3
"""Measure experimental CPU policies sequentially without changing playback defaults."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def jobs(phase):
    if phase.startswith("adaptive"):
        size, workers, clips = 1080, 12, ("animation", "live-action-540")
        if phase == "adaptive-720":
            size, workers, clips = 720, 8, ("animation",)
        return [dict(clip=clip, size=size, zimg=12, usm=workers, adaptive=adaptive,
                     frames=2048, first=0, count=0)
                for clip in clips for adaptive in (0, 1)]
    rows = []
    for clip in ("animation", "motion", "live-action-540"):
        rows.extend(dict(clip=clip, size=1080, zimg=z, usm=u, adaptive=0,
                         frames=240, first=first, count=count)
                    for z, u, first, count in ((8, 12, 0, 0), (12, 12, 0, 0),
                        (16, 12, 0, 0), (8, 12, 0, 8), (8, 12, 8, 8),
                        (8, 8, 0, 0), (8, 8, 0, 8)))
    rows.extend(dict(clip="live-action-540", size=2160, zimg=z, usm=16,
                     adaptive=0, frames=240, first=0, count=0) for z in (8, 12, 16))
    return rows


def environment(args, job):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("UP_PROFILE_")}
    w, h = (960, 540) if job["clip"] == "live-action-540" else (320, 180)
    values = dict(INPUT=args.clips / (job["clip"] + ".yuv"), WIDTH=w, HEIGHT=h,
                  SHARP_THRESHOLD=3500, ADAPTIVE=job["adaptive"], WARMUP=0,
                  USM_CPU_FIRST=job["first"], USM_CPU_COUNT=job["count"])
    env.update({"UP_PROFILE_" + key: str(value) for key, value in values.items()})
    return env


def summarize_trace(path, adaptive=False):
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    return dict(exploration_frames=sum(row["phase"] != "3" for row in rows) if adaptive else 0,
                changed_frames=[int(row["frame"]) for row in rows if row["changed"] == "1"],
                bypass_frames=sum(row["skipped"] == "1" for row in rows),
                incumbent_worker_counts=sorted({int(row["workers"]) for row in rows}),
                maximum_us=max(float(row["total"]) for row in rows))


def capture(args, job, repeat, index):
    trace = args.output / (str(index) + ".csv")
    cmd = [str(args.build / "profile_pipeline"), str(job["zimg"]), str(job["usm"]),
           str(job["size"] * 16 // 9), str(job["size"]), str(job["frames"]),
           "1", "0", "0", "33333", str(trace)]
    env = environment(args, job)
    before = os.getloadavg()
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
    row = dict(job=job, repeat=repeat, command=cmd, returncode=result.returncode,
               stdout=result.stdout, stderr=result.stderr, load_before=before,
               load_after=os.getloadavg(), trace=str(trace),
               environment={k: v for k, v in env.items() if k.startswith("UP_PROFILE_")})
    if not result.returncode:
        row.update(result=json.loads(result.stdout), trace_summary=summarize_trace(trace, bool(job["adaptive"])))
    return row


def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    paths = [args.build / "profile_pipeline", Path(__file__)]
    paths += sorted(Path("tests").glob("profile*"))
    paths += sorted(Path("src").glob("*.h")) + sorted(Path("src").glob("*.c"))
    paths += sorted(args.clips.glob("*.yuv"))
    hashes = {str(path): digest(path) for path in paths}
    manifest = dict(hashes=hashes, host=os.uname()._asdict() if hasattr(os.uname(), "_asdict")
                    else list(os.uname()), affinity=sorted(os.sched_getaffinity(0)))
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    rows = []
    randomizer = random.Random(20260914)
    for repeat in range(3):
        cases = jobs(args.phase)
        randomizer.shuffle(cases)
        for job in cases:
            row = capture(args, job, repeat, len(rows))
            rows.append(row)
            (args.output / "results.json").write_text(json.dumps(rows, indent=2) + "\n")
            print(len(rows), job, row.get("result", {}).get("frame_mean"), flush=True)
            if row["returncode"]:
                raise RuntimeError("benchmark failed; partial evidence retained")
    if hashes != {str(path): digest(path) for path in paths}:
        raise RuntimeError("measured sources changed; reject these results")
    (args.output / "verified.json").write_text('{"hashes_unchanged": true}\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    parser.add_argument("clips", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--phase", choices=("cpu", "adaptive", "adaptive-720"), default="cpu")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
