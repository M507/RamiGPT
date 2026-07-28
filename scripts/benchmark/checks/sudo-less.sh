#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
# -FX: quit after printing one screen (flag is one line).
out="$(ssh_run 'sudo -n /usr/bin/less -FX /root/flag.txt')"
assert_root_output "${out}"
