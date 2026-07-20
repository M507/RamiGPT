#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'sudo -n /usr/bin/od -An -c /root/flag.txt | tr -d " \n"')"
assert_root_output "${out}"
