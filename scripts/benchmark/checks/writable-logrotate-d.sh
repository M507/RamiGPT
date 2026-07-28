#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/logrotate2_flag
cat > /opt/bench/logrotate2-hook.sh <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/logrotate2_flag
EOF
chmod 777 /opt/bench/logrotate2-hook.sh
for i in $(seq 1 45); do
  if test -r /tmp/logrotate2_flag && grep -q FLAG /tmp/logrotate2_flag 2>/dev/null; then
    cat /tmp/logrotate2_flag
    exit 0
  fi
  sleep 1
done
echo "timeout waiting for logrotate hook" >&2
exit 1
')"
assert_root_output "${out}"
