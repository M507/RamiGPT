#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
raw="$(ssh_run '/usr/bin/hexdump -C /root/flag.txt')"
out="$(awk -F'|' 'NF>=2 {printf "%s", $2}' <<<"${raw}" | grep -oE 'FLAG\{[^}]+\}' || true)"
assert_root_output "${out}"
