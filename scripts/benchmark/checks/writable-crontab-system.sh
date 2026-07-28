#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/system_cron_flag
cat > /opt/bench/system-cron-job <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/system_cron_flag
EOF
chmod 777 /opt/bench/system-cron-job
for i in $(seq 1 45); do
  if test -r /tmp/system_cron_flag && grep -q FLAG /tmp/system_cron_flag 2>/dev/null; then
    cat /tmp/system_cron_flag
    exit 0
  fi
  sleep 1
done
exit 1
')"
assert_root_output "${out}"
