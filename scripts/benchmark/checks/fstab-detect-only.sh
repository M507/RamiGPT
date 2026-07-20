#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'head -1 /opt/bench/fstab.txt 2>/dev/null')"
if [[ -n "${out}" ]]; then
  echo "DETECT_OK: fstab ${out}"
  exit 0
fi
echo "FAIL: no fstab signal" >&2
exit 1
