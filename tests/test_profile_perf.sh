#!/usr/bin/env bash
set -euo pipefail

repo_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
fixture=$(mktemp -d "${TMPDIR:-/tmp}/vlc-profile-perf.XXXXXXXX")
trap 'rm -rf -- "$fixture"' EXIT
mkdir -p "$fixture/bin" "$fixture/build"
touch "$fixture/ready"
cat > "$fixture/build/profile_pipeline" <<'EOF'
#!/bin/sh
exit 0
EOF
cat > "$fixture/bin/id" <<'EOF'
#!/bin/sh
printf '0\n'
EOF
cat > "$fixture/bin/chown" <<'EOF'
#!/bin/sh
exit 0
EOF
cat > "$fixture/bin/perf" <<'EOF'
#!/usr/bin/env bash
set -eu
if [[ ${1:-} == c2c && ${2:-} == record ]]; then
    system_wide=0
    for arg in "$@"; do
        if [[ $arg == -a ]]; then system_wide=1; fi
    done
    if [[ $system_wide != 1 ]]; then
        echo "Invalid event (ibs_op//) in per-thread mode, enable system wide with '-a'." >&2
        exit 1
    fi
    if [[ ${PERF_FIXTURE_FAIL:-0} == 1 ]]; then exit 1; fi
fi
printf 'fixture perf output\n'
EOF
chmod +x "$fixture/bin/"* "$fixture/build/profile_pipeline"

collect() {
    PATH="$fixture/bin:$PATH" SUDO_USER=fixture SUDO_UID=1000 SUDO_GID=1000 \
        PERF_FIXTURE_FAIL="$2" bash "$repo_root/scripts/profile_perf.sh" \
        "$fixture/build" "$fixture/$1" "$fixture/ready" attribution \
        > "$fixture/$1.log" 2>&1
}

failures=0
if ! collect success 0 || [[ ! -s $fixture/success/w12.c2c.txt \
                         || ! -s $fixture/success/w32.c2c.txt ]]; then
    echo 'FAIL PERF-12: attribution must collect IBS in system-wide mode' >&2
    failures=$((failures + 1))
fi
if collect unavailable 1; then
    echo 'FAIL PERF-12: missing attribution data must return failure' >&2
    failures=$((failures + 1))
fi
if [[ ! -s $fixture/unavailable/status || ! -e $fixture/unavailable/done ]]; then
    echo 'FAIL PERF-12: failed capture must retain completion status' >&2
    failures=$((failures + 1))
fi
test "$failures" -eq 0
echo 'PERF-12 capture regression checks OK'
