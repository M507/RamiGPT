#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'cat /opt/bench/cgroup-surface.txt 2>/dev/null')"
if [[ -n "${out}" ]]; then echo "DETECT_OK: cgroup"; exit 0; fi
echo "FAIL: no detect signal" >&2; exit 1
