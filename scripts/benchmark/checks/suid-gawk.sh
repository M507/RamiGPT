#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '/usr/bin/gawk "{print}" /root/flag.txt')"
assert_root_output "${out}"
