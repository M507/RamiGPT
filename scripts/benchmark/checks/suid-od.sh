#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '/usr/bin/od -An -tx1 /root/flag.txt | tr -d " \n" | xxd -r -p')"
assert_root_output "${out}"
