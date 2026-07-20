#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '/usr/bin/less -f -R /root/flag.txt </dev/null 2>/dev/null | tr -d '\r'')"
assert_root_output "${out}"
