#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'sudo -n /usr/bin/openssl enc -in /root/flag.txt 2>/dev/null')"
assert_root_output "${out}"
