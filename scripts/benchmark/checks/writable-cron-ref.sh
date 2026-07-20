#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/cronref_flag
cat > /opt/bench/cronroot.sh <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/cronref_flag
EOF
chmod 777 /opt/bench/cronroot.sh
for i in $(seq 1 45); do
  if test -r /tmp/cronref_flag && grep -q FLAG /tmp/cronref_flag 2>/dev/null; then
    cat /tmp/cronref_flag
    exit 0
  fi
  sleep 1
done
echo "timeout waiting for cronroot.sh" >&2
grep cronroot /etc/crontab 2>&1 || true
ls -la /opt/bench/cronroot.sh /tmp/cronref_flag 2>&1 || true
exit 1
')"
assert_root_output "${out}"
