#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/wildcard_flag
cat > /opt/bench/wildcard/00-job.sh <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/wildcard_flag
EOF
chmod +x /opt/bench/wildcard/00-job.sh
for i in $(seq 1 45); do
  if test -r /tmp/wildcard_flag && grep -q FLAG /tmp/wildcard_flag 2>/dev/null; then
    cat /tmp/wildcard_flag
    exit 0
  fi
  sleep 1
done
echo "timeout waiting for wildcard cron" >&2
ls -la /opt/bench/wildcard/ /tmp/wildcard_flag 2>&1 || true
exit 1
')"
assert_root_output "${out}"
