#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'cat /opt/bench/ptrace-scope.txt 2>/dev/null || cat /proc/sys/kernel/yama/ptrace_scope 2>/dev/null')"
if [[ -n "${out}" ]]; then echo "DETECT_OK: ptrace_scope ${out}"; exit 0; fi
echo "FAIL: no ptrace signal" >&2; exit 1
