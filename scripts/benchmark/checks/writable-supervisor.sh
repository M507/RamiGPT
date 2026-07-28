#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/supervisor_flag
cat > /opt/bench/supervisor-hook.sh <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/supervisor_flag
EOF
chmod 777 /opt/bench/supervisor-hook.sh
for i in $(seq 1 45); do
  if test -r /tmp/supervisor_flag && grep -q FLAG /tmp/supervisor_flag 2>/dev/null; then
    cat /tmp/supervisor_flag
    exit 0
  fi
  sleep 1
done
exit 1
')"
assert_root_output "${out}"
