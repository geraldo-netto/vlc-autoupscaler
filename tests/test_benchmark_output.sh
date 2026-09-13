#!/usr/bin/env bash
set -eu

build=${1:?benchmark build directory required}
unset UP_PROFILE_INPUT UP_PROFILE_WIDTH UP_PROFILE_HEIGHT UP_PROFILE_EXECUTOR
unset UP_PROFILE_ACTIVE UP_PROFILE_ZEROCOPY UP_PROFILE_SHARP_THRESHOLD
unset UP_PROFILE_ADAPTIVE UP_PROFILE_WARMUP UP_PROFILE_USM_CPU_FIRST UP_PROFILE_USM_CPU_COUNT
failures=0

check_output_failure() {
    if ! "$@" >/dev/null; then
        printf 'OBS-18: benchmark baseline failed: %s\n' "$1" >&2
        failures=$((failures + 1))
        return
    fi
    if "$@" 1>&- 2>/dev/null; then
        printf 'OBS-18: missing output accepted: %s\n' "$1" >&2
        failures=$((failures + 1))
    fi
}

check_output_failure "$build/bench_adaptive" 1 1024 64 64 1
check_output_failure "$build/profile_pipeline" 1 1 64 64 1 0 0 0 0
if [[ $failures != 0 ]]; then exit 1; fi
printf 'OBS-18 benchmark output failure checks OK\n'
