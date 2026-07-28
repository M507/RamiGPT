#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/crontab_flag
cat > /opt/bench/job.sh <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/crontab_flag
EOF
chmod 777 /opt/bench/job.sh
for i in $(seq 1 45); do
  if test -r /tmp/crontab_flag && grep -q FLAG /tmp/crontab_flag 2>/dev/null; then
    cat /tmp/crontab_flag
    exit 0
  fi
  sleep 1
done
echo "timeout waiting for cron job.sh" >&2
ls -la /opt/bench/job.sh /etc/cron.d/bench-job /tmp/crontab_flag 2>&1 || true
exit 1
')"
assert_root_output "${out}"
