#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '/usr/bin/ptx -w 999 /root/flag.txt')"
assert_root_output "${out}"
