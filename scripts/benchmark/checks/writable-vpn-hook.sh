#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/vpn_flag
cat > /etc/openvpn/client/up.sh <<'\''EOF'\''
#!/bin/sh
cat /root/flag.txt > /tmp/vpn_flag
EOF
chmod 777 /etc/openvpn/client/up.sh
for i in $(seq 1 45); do
  if test -r /tmp/vpn_flag && grep -q FLAG /tmp/vpn_flag 2>/dev/null; then
    cat /tmp/vpn_flag
    exit 0
  fi
  sleep 1
done
exit 1
')"
assert_root_output "${out}"
