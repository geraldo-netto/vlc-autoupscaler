#!/bin/sh
set -eu

repo_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
halo="$repo_root/scripts/bench_usm_halo.sh"
isa="$repo_root/scripts/bench_usm_isa.sh"
tmp=$(mktemp -d "${TMPDIR:-/tmp}/vlc-autoscaler-bench-usm.XXXXXX")
fake="$tmp/bench path/fake-benchmark[*?]"

cleanup() {
    rm -rf -- "$tmp"
}
trap 'cleanup; exit 129' HUP
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM
trap cleanup EXIT

fail() {
    echo "USM benchmark script test failed: $*" >&2
    exit 1
}

mkdir -p "$(dirname -- "$fake")"
cat >"$fake" <<'EOF'
#!/bin/sh
set -eu
printf '%s,%s,%s,%s,%s,%s,%s,1.00\n' \
    "$1" "${EFFECTIVE_THREADS:-$1}" "$2" "$3" "$4" "$5" "$6"
EOF
chmod 0755 "$fake"

"$halo" "$fake" 7 19 >"$tmp/halo.csv"
test "$(wc -l <"$tmp/halo.csv")" -eq 25 || fail "halo row count"
awk -F, '
    NR == 1 { if ($0 != "alias,requested_threads,effective_threads,width,height,frames,amount,fill,us_per_frame") exit 1; next }
    NF != 9 || ($1 != "out" && $1 != "in") || $2 !~ /^[0-9]+$/ ||
        $3 != $2 || $4 !~ /^[0-9]+$/ || $5 !~ /^[0-9]+$/ || $6 != 7 || $7 != 19 ||
        $8 != "rand" || $9 != "1.00" { exit 1 }
    { rows++ }
    END { exit rows != 24 }
' "$tmp/halo.csv" || fail "halo CSV schema"

EFFECTIVE_THREADS=1 "$halo" "$fake" 7 19 >"$tmp/fallback.csv"
awk -F, 'NR > 1 && $3 != 1 { exit 1 }' "$tmp/fallback.csv" ||
    fail 'REV-16: effective fallback count lost'
grep -q '^out,4,1,' "$tmp/fallback.csv" || fail 'REV-16: requested count lost'

cat >"$tmp/invalid" <<'EOF'
#!/bin/sh
case $BAD_ROW in
    mismatch) effective=$1; if [ "$7" = in ]; then effective=1; fi
        printf '%s,%s,%s,%s,%s,%s,rand,1.00\n' "$1" "$effective" "$2" "$3" "$4" "$5" ;;
    *) printf '%s\n' "$BAD_ROW" ;;
esac
EOF
chmod +x "$tmp/invalid"
for row in '' garbage '1,1,1280,720,7,19,rand,nan' \
    '1,0,1280,720,7,19,rand,1' '1,2,1280,720,7,19,rand,1' \
    '1,1,1280,720,8,19,rand,1' mismatch; do
    if BAD_ROW="$row" "$halo" "$tmp/invalid" 7 19 >"$tmp/bad.csv" 2>/dev/null; then
        fail "REV-16: malformed or incomparable pair accepted: $row"
    fi
done

"$isa" "$fake" "$fake" "$fake" >"$tmp/isa.csv"
test "$(wc -l <"$tmp/isa.csv")" -eq 37 || fail "ISA row count"
awk -F, '
    NR == 1 { if ($0 != "isa,requested_threads,effective_threads,width,height,frames,amount,fill,us_per_frame") exit 1; next }
    NF != 9 || ($1 != "sse2" && $1 != "avx2" && $1 != "avx512") ||
        $2 !~ /^[0-9]+$/ || $3 !~ /^[0-9]+$/ || $4 !~ /^[0-9]+$/ ||
        $5 !~ /^[0-9]+$/ || $6 != 300 || $7 != 20 || $8 != "rand" ||
        $9 != "1.00" { exit 1 }
    { rows++ }
    END { exit rows != 36 }
' "$tmp/isa.csv" || fail "ISA CSV schema"

echo "USM benchmark script checks OK"
