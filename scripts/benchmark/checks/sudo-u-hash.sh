#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'sudo -l 2>/dev/null; sudo -V 2>/dev/null | head -1')"
if grep -Fq '(ALL, !root)' <<<"${out}"; then
  echo "DETECT_OK: sudoers (ALL, !root) rule present"
  exit 0
fi
echo "FAIL: expected (ALL, !root) sudoers rule" >&2
echo "${out}" >&2
exit 1
assert_root_output "${out}"
