#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'uname -r')"
if [[ -n "${out}" ]]; then
  echo "DETECT_OK: kernel version ${out}"
  exit 0
fi
echo "FAIL: no kernel version" >&2
exit 1

