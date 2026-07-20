#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'rm -f /home/lowpriv/rsflag; /usr/bin/rsync --chmod=644 /root/flag.txt /home/lowpriv/rsflag; cat /home/lowpriv/rsflag')"
assert_root_output "${out}"
