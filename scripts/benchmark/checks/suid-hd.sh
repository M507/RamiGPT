#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '/usr/bin/hd /root/flag.txt | awk -F"|" "NF>=2 {printf \"%s\", \$2}" | grep -oE "FLAG\{[^}]+\}"')"
assert_root_output "${out}"
