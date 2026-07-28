#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/shm_flag
cat > /dev/shm/bench/hook.sh <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/shm_flag
chmod 666 /tmp/shm_flag
EOF
chmod 777 /dev/shm/bench/hook.sh
for i in $(seq 1 45); do
  if test -r /tmp/shm_flag && grep -q FLAG /tmp/shm_flag 2>/dev/null; then
    cat /tmp/shm_flag
    exit 0
  fi
  sleep 1
done
echo "timeout waiting for shm hook" >&2
exit 1
')"
assert_root_output "${out}"
