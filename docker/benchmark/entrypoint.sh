#!/bin/bash
# Shared SSH entrypoint for benchmark privilege-escalation targets.
set -euo pipefail

BENCH_USER="${BENCH_USER:-zeus}"
BENCH_PASS="${BENCH_PASS:-benchmark}"

if ! id -u "${BENCH_USER}" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "${BENCH_USER}"
fi
echo "${BENCH_USER}:${BENCH_PASS}" | chpasswd

mkdir -p /var/run/sshd
ssh-keygen -A >/dev/null 2>&1 || true

# Password auth for benchmark SSH
sed -i 's/#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
sed -i 's/#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/#\?ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/' /etc/ssh/sshd_config
grep -q '^UsePAM' /etc/ssh/sshd_config || echo 'UsePAM yes' >> /etc/ssh/sshd_config

exec /usr/sbin/sshd -D -e
