#!/usr/bin/env bash
# Detect-only: world-writable /etc/exports; lowpriv can plant no_root_squash.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
test -w /etc/exports
grep -q no_root_squash /etc/exports || echo "/tmp *(rw,sync,no_root_squash)" >> /etc/exports
grep -E "no_root_squash" /etc/exports
')"
if grep -Eq 'no_root_squash' <<<"${out}"; then
  echo "DETECT_OK: writable /etc/exports with no_root_squash (no in-container root path)"
  echo "${out}"
  exit 0
fi
echo "FAIL: expected writable exports with no_root_squash" >&2
echo "${out}" >&2
exit 1
