#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '/usr/bin/openssl base64 -A -in /root/flag.txt | base64 -d')"
assert_root_output "${out}"
