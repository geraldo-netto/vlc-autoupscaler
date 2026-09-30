#!/bin/sh
set -eu

bin=${1:?bench binary path required}
frames=${2:-300}
amount=${3:-20}

validate_row() {
    printf '%s\n' "$1" | awk -F, -v workers="$threads" -v width="$width" \
        -v height="$height" -v frames="$frames" -v amount="$amount" '
        NF != 8 || $1 != workers || $2 !~ /^[0-9]+$/ || $2 < 1 || $2 > workers ||
        $3 != width || $4 != height || $5 != frames || $6 != amount || $7 != "rand" ||
        $8 !~ /^[0-9]+([.][0-9]+)?$/ { bad=1 }
        END { if (bad || NR != 1) exit 1; print $2 }
    ' || { echo 'invalid halo benchmark row' >&2; return 1; }
}

printf '%s\n' 'alias,requested_threads,effective_threads,width,height,frames,amount,fill,us_per_frame'
for size in '1280 720' '1920 1080' '2560 1440'; do
    width=${size% *}
    height=${size#* }
    for threads in 1 4 8 12; do
        for alias in out in; do
            row=$("$bin" "$threads" "$width" "$height" \
                "$frames" "$amount" rand "$alias")
            effective=$(validate_row "$row")
            if [ "$alias" = out ]; then
                out_effective=$effective
            elif [ "$effective" != "$out_effective" ]; then
                echo 'halo pair has different effective worker counts' >&2
                exit 1
            fi
            printf '%s,%s\n' "$alias" "$row"
        done
    done
done
