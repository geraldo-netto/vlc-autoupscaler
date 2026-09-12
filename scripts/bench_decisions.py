#!/usr/bin/env python3
"""Reproduce the September 2026 decision experiments; no production settings change."""
import argparse
import itertools
import json
import os
from pathlib import Path
import random
import subprocess


def configuration(group, clip, size, usm, **options):
    return dict(group=group, clip=clip, size=size, usm=usm, **options)


def configurations():
    cases = []
    for clip in ("animation", "motion", "live-action"):
        for usm in (8, 12):
            cases.append(configuration("presets", clip, 720, usm))
    for usm in (12, 16):
        cases.append(configuration("presets", "live-action-540", 2160, usm))
    for size, clip in ((720, "animation"), (2160, "live-action-540")):
        for pin, zerocopy in ((0, 1), (1, 1), (1, 0)):
            cases.append(configuration("pin-copy", clip, size, 12, pin=pin, zerocopy=zerocopy))
    for grid, executor in itertools.product((12, 32), (0, 1, 2)):
        cases.append(configuration("notification", "live-action", 720, grid,
                                   grid=grid, executor=executor))
    for active, executor in itertools.product((4, 8, 12), (1, 2)):
        cases.append(configuration("fixed-grid", "live-action", 720, 12,
                                   active=active, executor=executor))
    return cases


def run_pipeline(arguments, case, repeat, frames=240):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("UP_PROFILE_")}
    source = (960, 540) if case["size"] == 2160 else (320, 180)
    env.update(UP_PROFILE_INPUT=str(arguments.clips / (case["clip"] + ".yuv")),
               UP_PROFILE_WIDTH=str(source[0]), UP_PROFILE_HEIGHT=str(source[1]),
               UP_PROFILE_SHARP_THRESHOLD="3500",
               UP_PROFILE_EXECUTOR=str(case.get("executor", 0)),
               UP_PROFILE_ACTIVE=str(case.get("active", 0)),
               UP_PROFILE_ZEROCOPY=str(case.get("zerocopy", 1)))
    trace = arguments.output / (case["group"] + "-" + str(repeat) + "-" +
                                 str(arguments.sequence) + ".csv")
    command = [str(arguments.build / "profile_pipeline"), str(case.get("grid", 12)),
               str(case["usm"]), str(case["size"] * 16 // 9), str(case["size"]),
               str(frames), str(case.get("pin", 1)), "0", "0",
               str(case.get("period", 16667)), str(trace)]
    result = subprocess.run(command, env=env, text=True, capture_output=True, check=True)
    record = dict(case, repeat=repeat, frames=frames, command=command,
                  environment={key: value for key, value in env.items()
                               if key.startswith("UP_PROFILE_")}, result=json.loads(result.stdout))
    with (arguments.output / "paced.jsonl").open("a") as stream:
        stream.write(json.dumps(record) + "\n")
    arguments.sequence += 1
    print(case["group"], repeat, arguments.sequence, flush=True)


def run_adaptive(arguments):
    rows = list(itertools.product(range(3), (2, 3), (0, 1), (12, -1)))
    random.Random(20260912).shuffle(rows)
    with (arguments.output / "adaptive.csv").open("w") as stream:
        stream.write("repeat,usm_request,frames,width,height,zimg_workers,effective_usm,"
                     "first_settled_frame,changes,total_us,tail_us,zimg_us,usm_us,algorithm,pin,outcome\n")
        for repeat, algorithm, pin, workers in rows:
            command = [str(arguments.build / "bench_adaptive"), str(workers), "4096",
                       "1920", "1080", "12", str(algorithm), str(pin)]
            result = subprocess.run(command, text=True, capture_output=True, check=True)
            stream.write(str(repeat) + "," + result.stdout)
            stream.flush()


def run_followup(arguments):
    arguments.sequence = len((arguments.output / "paced.jsonl").read_text().splitlines())
    randomizer = random.Random(20260913)
    for repeat in range(3):
        cases = [configuration("paired-native", "animation", 720, workers,
                               pin=pin, zerocopy=zerocopy, period=33333)
                 for workers, pin, zerocopy in ((8, 1, 1), (12, 1, 1),
                                                (12, 0, 1), (12, 1, 0))]
        randomizer.shuffle(cases)
        for case in cases:
            run_pipeline(arguments, case, repeat)
    for repeat in range(5):
        cases = [configuration("paired-notification", "live-action", 720, 32,
                               grid=32, executor=mode) for mode in (0, 2)]
        randomizer.shuffle(cases)
        for case in cases:
            run_pipeline(arguments, case, repeat)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    parser.add_argument("clips", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--followup", action="store_true")
    arguments = parser.parse_args()
    if arguments.followup:
        run_followup(arguments)
        return
    arguments.output.mkdir(parents=True, exist_ok=False)
    arguments.sequence = 0
    run_adaptive(arguments)
    rows = list(itertools.product(range(3), configurations()))
    random.Random(20260912).shuffle(rows)
    for repeat, case in rows:
        run_pipeline(arguments, case, repeat)
    for usm in (8, 12):
        run_pipeline(arguments, configuration("long-run", "motion", 720, usm), 0, 3600)


if __name__ == "__main__":
    main()
