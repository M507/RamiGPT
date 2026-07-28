#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'test -s /opt/bench/cap-hints.txt && wc -l < /opt/bench/cap-hints.txt')"
if [[ -n "${out}" && "${out}" != "0" ]]; then echo "DETECT_OK: cap hints ${out} lines"; exit 0; fi
echo "FAIL: no capability hints" >&2; exit 1
