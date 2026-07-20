#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/sshd_flag
cat > /opt/bench/sshd-hook.sh <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/sshd_flag
EOF
chmod 777 /opt/bench/sshd-hook.sh
for i in $(seq 1 45); do
  if test -r /tmp/sshd_flag && grep -q FLAG /tmp/sshd_flag 2>/dev/null; then
    cat /tmp/sshd_flag
    exit 0
  fi
  sleep 1
done
exit 1
')"
assert_root_output "${out}"
