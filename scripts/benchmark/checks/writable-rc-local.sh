#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/rclocal_flag
cat > /etc/rc.local <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/rclocal_flag
exit 0
EOF
chmod 777 /etc/rc.local
for i in $(seq 1 45); do
  if test -r /tmp/rclocal_flag && grep -q FLAG /tmp/rclocal_flag 2>/dev/null; then
    cat /tmp/rclocal_flag
    exit 0
  fi
  sleep 1
done
exit 1
')"
assert_root_output "${out}"
