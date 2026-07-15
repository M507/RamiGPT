#!/bin/bash
# Bind sshd on SSH_PORT on all IPv4 interfaces (host networking — no DNAT).
# Same listen pattern for every bench container (see bench-sudo-vim).
set -euo pipefail

SSH_PORT="${SSH_PORT:-22}"

if ! [[ "${SSH_PORT}" =~ ^[0-9]+$ ]] || (( SSH_PORT < 1 || SSH_PORT > 65535 )); then
  echo "Invalid SSH_PORT=${SSH_PORT}" >&2
  exit 1
fi

/apply-misconfig.sh

# Normalize listen config: IPv4 only, all interfaces, exact port.
sed -i -E \
  -e '/^#?Port[[:space:]]+/d' \
  -e '/^#?ListenAddress[[:space:]]+/d' \
  -e '/^#?AddressFamily[[:space:]]+/d' \
  /etc/ssh/sshd_config

{
  echo "Port ${SSH_PORT}"
  echo "AddressFamily inet"
  echo "ListenAddress 0.0.0.0"
} >> /etc/ssh/sshd_config

mkdir -p /var/run/sshd
exec /usr/sbin/sshd -D -e
