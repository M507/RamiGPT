#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/logrotate_flag
cat > /opt/bench/logrotate-hook.sh <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/logrotate_flag
EOF
chmod 777 /opt/bench/logrotate-hook.sh
for i in $(seq 1 45); do
  if test -r /tmp/logrotate_flag && grep -q FLAG /tmp/logrotate_flag 2>/dev/null; then
    cat /tmp/logrotate_flag
    exit 0
  fi
  # nudge logrotate when the log is large enough to rotate
  dd if=/dev/zero bs=1024 count=2 >> /var/log/bench/app.log 2>/dev/null || true
  sleep 1
done
echo "timeout waiting for logrotate hook" >&2
exit 1
')"
assert_root_output "${out}"
