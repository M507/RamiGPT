#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '/usr/bin/perl -e "print do{local \$/; open F,\"/root/flag.txt\"; <F>}"')"
assert_root_output "${out}"
