#!/usr/bin/env python3
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def environment():
    result = os.environ.copy()
    for name in ("MAKEFLAGS", "MFLAGS", "MAKELEVEL"):
        result.pop(name, None)
    return result


def canonical_targets():
    rule = "fuzz-test-list:;@printf '%s\\n' $(FUZZ_TARGET_NAMES)"
    output = subprocess.check_output(
        ["make", "--no-print-directory", "-s", "--eval", rule, "fuzz-test-list"],
        cwd=ROOT, env=environment(), text=True)
    return output.split()


def check_workflow(targets):
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    if "run: make run-fuzz" in workflow:
        return
    declared = set(re.findall(r"build/fuzz_(\w+)", workflow))
    for group in re.findall(r"for t in (.*?); do", workflow, re.S):
        declared.update(re.findall(r"\b[a-z][a-z_]+\b", group))
    missing = sorted(set(targets) - declared)
    raise AssertionError(f"BUILD-38: CI lacks canonical runner; unexecuted={missing}")


def check_invocations(targets, log):
    calls = [line.split("|", 1) for line in log.read_text().splitlines()]
    names = [name.removeprefix("fuzz_") for name, _ in calls]
    assert sorted(names) == sorted(targets), ("BUILD-38", names, targets)
    arguments = dict(calls)
    assert "-max_total_time=30" in arguments["fuzz_plane_buffer"]
    for name, duration, length in (("upscale_logic", 60, 24), ("usm", 60, 64),
                                    ("scaler_seam", 90, 10)):
        if name in targets:
            args = arguments["fuzz_" + name]
            assert f"-max_total_time={duration}" in args
            assert f"-max_len={length}" in args


def check_runner(targets):
    with tempfile.TemporaryDirectory(prefix="vlc-fuzz-runner-") as directory:
        build = Path(directory) / "build"
        build.mkdir()
        log = Path(directory) / "calls"
        for name in targets:
            binary = build / ("fuzz_" + name)
            binary.write_text('#!/bin/sh\nprintf "%s|%s\\n" "${0##*/}" "$*" '
                              '>> "$FUZZ_TEST_LOG"\n')
            binary.chmod(0o755)
        env = environment()
        env["FUZZ_TEST_LOG"] = str(log)
        subprocess.run(["make", "--no-print-directory", "-s", "-o", "fuzz",
                        "run-fuzz", f"BUILD={build}"],
                       cwd=ROOT, env=env, check=True)
        check_invocations(targets, log)


def main():
    targets = canonical_targets()
    check_workflow(targets)
    check_runner(targets)
    print("BUILD-38 canonical fuzzer execution checks OK")


if __name__ == "__main__":
    main()
