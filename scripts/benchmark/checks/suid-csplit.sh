#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'rm -f /tmp/csp*; /usr/bin/csplit -s -f /tmp/csp /root/flag.txt 1; cat /tmp/csp*')"
assert_root_output "${out}"
