#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '
for i in $(seq 1 60); do
  if [ -S /var/run/mysqld/mysqld.sock ]; then
    mysql -u root --socket=/var/run/mysqld/mysqld.sock -N -e "SELECT LOAD_FILE('\''/var/lib/mysql/flag.txt'\'');" 2>/dev/null && exit 0
  fi
  sleep 1
done
echo "mysql socket not ready" >&2
exit 1
')"
assert_root_output "${out}"
