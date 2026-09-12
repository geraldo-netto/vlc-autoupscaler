#!/usr/bin/env bash
set -euo pipefail

repo_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
build=${1:?fuzzer build directory required}
shift

target_profile() {
    case $1 in
        upscale_logic) printf '60 24 corpus\n' ;;
        usm) printf '60 64 -\n' ;;
        frame_shape) printf '60 24 corpus_frame_shape\n' ;;
        scaler_chroma) printf '60 17 corpus_scaler_chroma\n' ;;
        content_probe) printf '60 64 -\n' ;;
        usm_variants) printf '60 0 corpus_usm_variants\n' ;;
        scaler_seam) printf '90 10 corpus_scaler_seam\n' ;;
        *) printf '30 0 -\n' ;;
    esac
}

run_target() {
    local target=$1 duration length seeds
    read -r duration length seeds < <(target_profile "$target")
    local corpus="$build/fuzz-corpus/$target"
    mkdir -p -- "$corpus"
    if [[ $seeds != - ]]; then
        local seed
        for seed in "$repo_root/tests/$seeds/"*; do
            if [[ -f $seed ]]; then cp -- "$seed" "$corpus/"; fi
        done
    fi
    local args=("$corpus" "-max_total_time=$duration" -print_final_stats=1)
    if [[ $length != 0 ]]; then args+=("-max_len=$length"); fi
    "$build/fuzz_$target" "${args[@]}"
}

for target in "$@"; do run_target "$target"; done
