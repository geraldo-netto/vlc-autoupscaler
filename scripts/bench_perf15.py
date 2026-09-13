#!/usr/bin/env python3
"""Bounded PERF-15 paired latency trial; unchanged production defaults."""
import argparse
import csv
import json
import os
from pathlib import Path
import random
import subprocess

from bench_playback_policies import digest

CLIPS = ("animation", "motion", "live-action-540")
TREATMENTS = ("duplicate", "fixed4", "local", "adaptive", "latency")
METRICS = ("frame_mean", "frame_p95", "frame_p99", "processing_cpu_mean")


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def settings(clip, treatment):
    live = clip == "live-action-540"
    workers = 12 if live else 8
    return dict(clip=clip, treatment=treatment, width=960 if live else 320,
                height=540 if live else 180, size=1080 if live else 720,
                usm=4 if treatment == "fixed4" else workers,
                affinity=8 if treatment == "local" else 0,
                adaptive=int(treatment in ("adaptive", "latency")),
                binary="profile_pipeline_latency" if treatment == "latency" else "profile_pipeline")


def trace_summary(path, adaptive):
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    settled = sum(row["phase"] == "3" for row in rows) if adaptive else 0
    transitions = zip(rows, rows[1:])
    return dict(settled_frames=settled,
                exploration_frames=len(rows)-settled if adaptive else 0,
                restarts=sum(a["phase"] == "3" and b["phase"] != "3" for a, b in transitions),
                selected_workers=sorted({int(row["selected_workers"]) for row in rows}),
                changed_frames=[dict(frame=int(row["frame"]), us=float(row["total"]),
                                     workers=int(row["workers"])) for row in rows if row["changed"] == "1"])


def output_text(value):
    return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value or ''


def execute_capture(command, environment):
    try:
        result = subprocess.run(command, env=environment, capture_output=True, text=True,
                                errors='replace', timeout=150)
        return dict(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
    except subprocess.TimeoutExpired as error:
        return dict(returncode=-1, failure='timeout', timeout_seconds=error.timeout,
                    stdout=output_text(error.stdout), stderr=output_text(error.stderr))
    except OSError as error:
        return dict(returncode=-1, failure='launch', error=str(error), stdout='', stderr='')


def capture_configuration(build, clips, job, trace, pixels=False):
    frames, period = (600, 0) if pixels else (2700, 33333)
    cmd = [str(build/job["binary"]), "12", str(job["usm"]),
           str(job["size"]*16//9), str(job["size"]), str(frames), "1", "0", "0",
           str(period), str(trace)]
    values = dict(INPUT=clips/(job["clip"]+".yuv"), WIDTH=job["width"], HEIGHT=job["height"],
                  ADAPTIVE=job["adaptive"], WARMUP=0, SHARP_THRESHOLD=3500, ZEROCOPY=1,
                  USM_CPU_FIRST=0, USM_CPU_COUNT=job["affinity"], VERIFY_PIXELS=int(pixels),
                  EXECUTOR=0, ACTIVE=0)
    return cmd, {"UP_PROFILE_"+key: str(value) for key, value in values.items()}


def capture(args, job, index, pixels=False):
    trace = args.output / (str(index) + ".csv")
    cmd, controls = capture_configuration(args.build, args.clips, job, trace, pixels)
    env = {key: value for key, value in os.environ.items() if not key.startswith("UP_PROFILE_")}
    before = os.getloadavg()
    result = execute_capture(cmd, dict(env, **controls))
    row = dict(job=job, command=cmd, environment=controls, trace=trace.name,
               **result,
               load_before=before, load_after=os.getloadavg())
    return row


def parse_capture(row, directory):
    if row['returncode']:
        return
    try:
        result = json.loads(row['stdout'])
        if not isinstance(result, dict):
            raise ValueError('capture output must be a JSON object')
        summary = trace_summary(directory / row['trace'], row['job']['adaptive'])
        row.update(result=result, summary=summary)
    except (OSError, ValueError, KeyError, TypeError) as error:
        row.update(failure='output-parse', error=str(error))


def checked_capture(args, job, rows, pixels=False):
    row = capture(args, job, len(rows), pixels)
    rows.append(row)
    save(args.output/"results.json", rows)
    parse_capture(row, args.output)
    save(args.output/"results.json", rows)
    print(len(rows), job["clip"], job["treatment"], row.get("result", {}).get("frame_p99"), flush=True)
    if row["returncode"] or row.get('failure'):
        raise RuntimeError("capture failed; partial evidence retained")
    return row


def ratios(baseline, candidate):
    return {key: candidate["result"][key]/baseline["result"][key] for key in METRICS}


def guarded(ratio):
    return all(value <= 1.05 for value in ratio.values())


def pair(args, clip, treatment, repeat, order, rows):
    captured = {}
    for name in order:
        captured[name] = checked_capture(args, settings(clip, name), rows)
    return dict(clip=clip, treatment=treatment, repeat=repeat, order=order,
                baseline=captured["baseline"]["trace"], candidate=captured[treatment]["trace"],
                valid_outcomes=all(row["result"]["adaptive_outcome"] in ("fixed", "settled", "searching")
                                   for row in captured.values()),
                ratios=ratios(captured["baseline"], captured[treatment]))


def paired_plan():
    randomizer = random.Random(20260915)
    plan = []
    for repeat in range(3):
        jobs = [(clip, treatment) for clip in CLIPS for treatment in TREATMENTS]
        randomizer.shuffle(jobs)
        for clip, treatment in jobs:
            order = ["baseline", treatment]
            randomizer.shuffle(order)
            plan.append(dict(clip=clip, treatment=treatment, repeat=repeat, order=order))
    return plan


def compare(args):
    plan = paired_plan()
    save(args.output/"plan.json", plan)
    rows, pairs, skipped, rejected = [], [], [], set()
    for job in plan:
        if job["repeat"] and job["treatment"] in rejected:
            skipped.append(dict(**job, reason="guard or adaptive outcome failed in an earlier pair"))
            save(args.output/"skipped.json", skipped)
            continue
        result = pair(args, **job, rows=rows)
        pairs.append(result)
        save(args.output/"pairs.json", pairs)
        if job["treatment"] != "duplicate" and not pair_passes(result):
            rejected.add(job["treatment"])
    save(args.output/"skipped.json", skipped)
    save(args.output/"decision.json", decisions(pairs))


def pixel_hashes(path):
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 600
    hashes = [row["pixel_hash"] for row in rows]
    assert all(value != "0000000000000000" for value in hashes)
    return hashes


def verify_pixels(args):
    rows, checks = [], []
    for clip in CLIPS:
        base = checked_capture(args, settings(clip, "baseline"), rows, True)
        expected = pixel_hashes(args.output/base["trace"])
        for treatment in TREATMENTS:
            row = checked_capture(args, settings(clip, treatment), rows, True)
            matches = pixel_hashes(args.output/row["trace"]) == expected
            checks.append(dict(clip=clip, treatment=treatment, frames=600, hashes_match=matches))
            save(args.output/"pixels.json", checks)
            if not matches:
                raise RuntimeError("pixel control differs; do not promote this policy")


def control_noise(pairs):
    controls = [row for row in pairs if row["treatment"] == "duplicate"]
    return {clip: max(abs(row["ratios"]["frame_p99"]-1) for row in controls if row["clip"] == clip)
            for clip in CLIPS}


def candidate_decision(pairs, treatment, noise):
    rows = [row for row in pairs if row["treatment"] == treatment]
    good = [clip for clip in CLIPS if qualifying(rows, clip, noise[clip])]
    guards = all(pair_passes(row) for row in rows)
    return dict(treatment=treatment, paired_runs=len(rows), guards_pass=guards,
                qualifying_workloads=good, promote=guards and len(rows) == 9 and bool(good))


def decisions(pairs):
    noise = control_noise(pairs)
    return dict(p99_control_noise=noise,
                decisions=[candidate_decision(pairs, treatment, noise) for treatment in TREATMENTS[1:]])


def qualifying(rows, clip, noise):
    values = [row["ratios"]["frame_p99"] for row in rows if row["clip"] == clip]
    return len(values) == 3 and all(value <= .9 and 1-value > noise for value in values)


def pair_passes(row):
    return row["valid_outcomes"] and guarded(row["ratios"])


def manifest(args):
    files = [args.build/"profile_pipeline", args.build/"profile_pipeline_latency",
             Path("Makefile"), Path("docs/PERF15_LATENCY_TRIAL.md")]
    files += sorted(Path("src").glob("*.[ch]")) + sorted(Path("tests").glob("*.[ch]"))
    files += sorted(Path("scripts").glob("*.py"))
    files += [args.clips/(clip+".yuv") for clip in CLIPS]
    return dict(hashes={str(file): digest(file) for file in files},
                host=list(os.uname()), affinity=sorted(os.sched_getaffinity(0)))


def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    before = manifest(args)
    save(args.output/"manifest.json", before)
    if args.pixels:
        verify_pixels(args)
    else:
        compare(args)
    if before != manifest(args):
        raise RuntimeError("measured sources or inputs changed; reject this matrix")
    save(args.output/"verified.json", dict(hashes_unchanged=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    parser.add_argument("clips", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--pixels", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
