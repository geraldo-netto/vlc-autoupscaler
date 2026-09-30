#!/usr/bin/env bash
set -eu

build=${1:?benchmark build directory required}
mode=${2:-zimg}
temporary=$(mktemp -d)
trap 'rm -rf -- "$temporary"' EXIT
unset UP_PROFILE_INPUT UP_PROFILE_WIDTH UP_PROFILE_HEIGHT UP_PROFILE_EXECUTOR
unset UP_PROFILE_ACTIVE UP_PROFILE_ZEROCOPY UP_PROFILE_SHARP_THRESHOLD
unset UP_PROFILE_ADAPTIVE UP_PROFILE_WARMUP UP_PROFILE_USM_CPU_FIRST UP_PROFILE_USM_CPU_COUNT
unset UP_PROFILE_VERIFY_PIXELS
failures=0

check_output_failure() {
    if ! "$@" >"$temporary/stdout" || [[ ! -s $temporary/stdout ]]; then
        printf 'OBS-18: benchmark baseline failed: %s\n' "$1" >&2
        failures=$((failures + 1))
        return
    fi
    if "$@" 1>&- 2>/dev/null; then
        printf 'OBS-18: missing output accepted: %s\n' "$1" >&2
        failures=$((failures + 1))
    fi
    if [[ -e /dev/full ]] && "$@" >/dev/full 2>/dev/null; then
        printf 'REV-5: buffered output failure accepted: %s\n' "$1" >&2
        failures=$((failures + 1))
    fi
}

check_extra_arguments() {
    local status=0
    "$@" unexpected >"$temporary/stdout" 2>"$temporary/stderr" || status=$?
    if [[ $status != 2 || -s $temporary/stdout ]]; then
        printf 'REV-27: excess arguments accepted or measurements emitted: %s\n' "$1" >&2
        failures=$((failures + 1))
    fi
}

if [[ $mode == core ]]; then
check_output_failure "$build/profile_worker_pool" 1 1 0 0
check_output_failure "$build/bench_worker_pool" 1 1
check_output_failure "$build/bench_usm_pool" 1 64 64 1 20 rand
check_extra_arguments "$build/bench_usm_pool" 1 8 8 1 20 rand out
elif [[ $mode == zimg ]]; then
check_output_failure "$build/bench_adaptive" 1 1024 64 64 1
check_output_failure "$build/profile_pipeline" 1 1 64 64 1 0 0 0 0
check_output_failure "$build/bench_scaler_zimg" 1 i420 32 32 64 64 1
check_output_failure "$build/bench_pipeline" 1 1
check_extra_arguments "$build/bench_scaler_zimg" 1 i420 8 8 16 16 1 1 0
check_extra_arguments "$build/bench_pipeline" 1 1 0 0 0
elif [[ $mode == vulkan ]]; then
dd if=/dev/zero of="$temporary/input.yuv" bs=777600 count=1 2>/dev/null
check_output_failure "$build/bench_vulkan" "$build/vulkan_usm.spv" 0 64 64 1 1 0 gpu
check_output_failure "$build/bench_vulkan_scale" "$build/vulkan_spline36.spv" 0 2 gpu "$temporary/input.yuv"
else
    echo 'unknown benchmark output test mode' >&2
    exit 2
fi
if [[ $failures != 0 ]]; then exit 1; fi
printf 'OBS-18 benchmark output failure checks OK\n'
