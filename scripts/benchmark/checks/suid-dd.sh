#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '/bin/dd if=/root/flag.txt bs=256 count=1 2>/dev/null')"
assert_root_output "${out}"
