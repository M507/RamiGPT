#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/cronflag
cat > /opt/bench/cronjob <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/cronflag
EOF
chmod 777 /opt/bench/cronjob
for i in $(seq 1 45); do
  if test -r /tmp/cronflag && grep -q FLAG /tmp/cronflag 2>/dev/null; then
    cat /tmp/cronflag
    exit 0
  fi
  sleep 1
done
echo "timeout waiting for cron hook" >&2
exit 1
')"
assert_root_output "${out}"
