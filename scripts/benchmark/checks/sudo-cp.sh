#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'sudo -n /bin/cp /root/flag.txt /dev/stdout')"
assert_root_output "${out}"
