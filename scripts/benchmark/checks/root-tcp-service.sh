#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'curl -fsS "http://127.0.0.1:8877/run?cmd=cat+/root/flag.txt"')"
assert_root_output "${out}"
