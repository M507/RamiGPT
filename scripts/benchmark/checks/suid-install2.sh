#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'rm -f /home/lowpriv/flag.out; /usr/bin/install -m644 /root/flag.txt /home/lowpriv/flag.out; cat /home/lowpriv/flag.out')"
assert_root_output "${out}"
