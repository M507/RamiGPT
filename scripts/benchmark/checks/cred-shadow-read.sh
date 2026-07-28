#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'test -r /etc/shadow && grep -q "^root:" /etc/shadow && echo password | su - root -c "cat /root/flag.txt"')"
assert_root_output "${out}"
