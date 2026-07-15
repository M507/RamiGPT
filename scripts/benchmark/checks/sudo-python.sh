#!/usr/bin/env bash
# Expects root via: sudo python3 …
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'sudo -n /usr/bin/python3 -c "print(open(\"/root/flag.txt\").read())"')"
assert_root_output "${out}"
