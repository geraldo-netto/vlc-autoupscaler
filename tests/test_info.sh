#!/bin/sh
set -eu

repo_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
version=$(python3 - "$repo_root/src/version.h" <<'PY'
from datetime import date
from pathlib import Path
import re
import sys

source = Path(sys.argv[1]).read_text()
matches = re.findall(r'^#define UP_VERSION "([0-9]{4}-[0-9]{2}-[0-9]{2})"$', source, re.M)
if len(matches) != 1 or date.fromisoformat(matches[0]).isoformat() != matches[0]:
    raise SystemExit('plugin version must be a valid yyyy-mm-dd date')
print(matches[0])
PY
)

expect_line() {
    output=$1
    expected=$2
    if ! printf '%s\n' "$output" | grep -Fqx "$expected"; then
        echo "make info test failed: missing '$expected'" >&2
        exit 1
    fi
}

enabled=$(make -s -C "$repo_root" info HAVE_ZIMG=1 \
    MARCH=x86-64 MULTIVERSION=1)
expect_line "$enabled" "zimg backend   : ENABLED"
expect_line "$enabled" "Plugin version : $version"
expect_line "$enabled" "MARCH          : x86-64"
expect_line "$enabled" "MULTIVERSION   : 1"

disabled=$(make -s -C "$repo_root" info HAVE_ZIMG= \
    MARCH=x86-64-v3 MULTIVERSION=0)
expect_line "$disabled" "zimg backend   : disabled"
expect_line "$disabled" "Plugin version : $version"
expect_line "$disabled" "MARCH          : x86-64-v3"
expect_line "$disabled" "MULTIVERSION   : 0"

echo "make info configuration checks OK"
