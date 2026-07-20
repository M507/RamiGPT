#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'cat /opt/bench/docker-surface.txt 2>/dev/null')"
if grep -Eq 'docker-cli|docker-sock|lowpriv' <<<"${out}"; then echo "DETECT_OK: docker surface"; exit 0; fi
echo "FAIL: no docker surface" >&2; exit 1
