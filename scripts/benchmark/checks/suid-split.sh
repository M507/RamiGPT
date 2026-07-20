#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'rm -f /tmp/xaa; /usr/bin/split -b999 /root/flag.txt /tmp/x; cat /tmp/xaa')"
assert_root_output "${out}"
