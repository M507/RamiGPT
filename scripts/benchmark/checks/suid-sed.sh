#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '/usr/bin/sed -n "1,\$p" /root/flag.txt')"
assert_root_output "${out}"
