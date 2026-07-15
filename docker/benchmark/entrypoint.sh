#!/bin/bash
# Bind sshd (SSH_PORT) and apply MISCONFIG profile before listen.
set -euo pipefail

SSH_PORT="${SSH_PORT:-22}"

if ! [[ "${SSH_PORT}" =~ ^[0-9]+$ ]] || (( SSH_PORT < 1 || SSH_PORT > 65535 )); then
  echo "Invalid SSH_PORT=${SSH_PORT}" >&2
  exit 1
fi

/apply-misconfig.sh

if grep -qE '^#?Port[[:space:]]+' /etc/ssh/sshd_config; then
  sed -i -E "s/^#?Port[[:space:]]+.*/Port ${SSH_PORT}/" /etc/ssh/sshd_config
else
  echo "Port ${SSH_PORT}" >> /etc/ssh/sshd_config
fi

mkdir -p /var/run/sshd
exec /usr/sbin/sshd -D -e
