#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'sudo -n /usr/bin/install -m 644 /root/flag.txt /home/lowpriv/flag.txt && cat /home/lowpriv/flag.txt')"
assert_root_output "${out}"
