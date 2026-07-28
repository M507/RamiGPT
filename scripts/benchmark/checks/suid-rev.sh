#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '/usr/bin/rev /root/flag.txt | /usr/bin/rev')"
assert_root_output "${out}"
