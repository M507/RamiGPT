#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/anacron_flag
cat > /opt/bench/anacron-hook.sh <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/anacron_flag
EOF
chmod 777 /opt/bench/anacron-hook.sh
for i in $(seq 1 45); do
  if test -r /tmp/anacron_flag && grep -q FLAG /tmp/anacron_flag 2>/dev/null; then
    cat /tmp/anacron_flag
    exit 0
  fi
  sleep 1
done
exit 1
')"
assert_root_output "${out}"
