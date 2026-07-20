#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'NODE=$(command -v node || command -v nodejs); "$NODE" -e "console.log(require(\"fs\").readFileSync(\"/root/flag.txt\",\"utf8\"))"')"
assert_root_output "${out}"
