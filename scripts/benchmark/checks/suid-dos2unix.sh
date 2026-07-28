#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '/usr/bin/dos2unix -O /root/flag.txt 2>/dev/null')"
assert_root_output "${out}"
