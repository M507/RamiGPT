#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '/usr/bin/join -a1 -o1.1 /root/flag.txt /dev/null')"
assert_root_output "${out}"
