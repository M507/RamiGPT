#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'printf "1,\$p\nq\n" | /usr/bin/ed -s /root/flag.txt')"
assert_root_output "${out}"
