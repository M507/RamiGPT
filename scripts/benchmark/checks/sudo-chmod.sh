#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'sudo -n /bin/chmod 755 /root && sudo -n /bin/chmod 644 /root/flag.txt && cat /root/flag.txt')"
assert_root_output "${out}"
