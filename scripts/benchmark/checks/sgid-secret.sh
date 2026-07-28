#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '/opt/bench/sgidcat /var/bench/flagcopy')"
assert_root_output "${out}"
