#!/usr/bin/env bash
# Detect-only: confirms BeRoot-style NFS finding is present. Does NOT get root.
# Exit 0 = detection OK (still flagged as no-root by the runner).
# Exit 1 = broken profile.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'grep -E "no_root_squash" /etc/exports')"
if grep -Eq 'no_root_squash' <<<"${out}"; then
  echo "DETECT_OK: /etc/exports has no_root_squash (no in-container root path by design)"
  echo "${out}"
  exit 0
fi
echo "FAIL: expected no_root_squash in /etc/exports" >&2
echo "${out}" >&2
exit 1
