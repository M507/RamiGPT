#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/cron_d_flag
cat > /opt/bench/cron-d-job <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/cron_d_flag
EOF
chmod 777 /opt/bench/cron-d-job
for i in $(seq 1 45); do
  if test -r /tmp/cron_d_flag && grep -q FLAG /tmp/cron_d_flag 2>/dev/null; then
    cat /tmp/cron_d_flag
    exit 0
  fi
  sleep 1
done
exit 1
')"
assert_root_output "${out}"
