#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'sudo -n /bin/bash -c "cat /root/flag.txt"')"
assert_root_output "${out}"
