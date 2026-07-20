#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '/usr/bin/lua -e "print(io.open(\"/root/flag.txt\"):read(\"*a\"))"')"
assert_root_output "${out}"
