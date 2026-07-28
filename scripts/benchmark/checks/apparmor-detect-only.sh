#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'cat /opt/bench/apparmor-enabled.txt 2>/dev/null || cat /sys/module/apparmor/parameters/enabled 2>/dev/null || echo unavailable')"
if [[ -n "${out}" ]]; then
  echo "DETECT_OK: apparmor ${out}"
  exit 0
fi
echo "FAIL: no apparmor signal" >&2
exit 1
