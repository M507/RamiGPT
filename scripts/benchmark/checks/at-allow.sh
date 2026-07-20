#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/atflag
cat > /opt/bench/atjob <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/atflag
EOF
chmod 777 /opt/bench/atjob
for i in $(seq 1 60); do
  if test -r /tmp/atflag && grep -q FLAG /tmp/atflag 2>/dev/null; then
    cat /tmp/atflag
    exit 0
  fi
  sleep 1
done
echo "timeout waiting for at job" >&2
exit 1
')"
assert_root_output "${out}"
