#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '/usr/bin/gawk "BEGIN {while((getline l<\"/root/flag.txt\")>0) print l}"')"
assert_root_output "${out}"
