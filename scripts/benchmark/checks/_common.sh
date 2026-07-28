#!/usr/bin/env bash
# Shared helpers for scripts/benchmark/checks/*.sh
# Required env: BENCH_HOST BENCH_PORT BENCH_USER BENCH_PASS
# Optional: BENCH_FLAG BENCH_TIMEOUT SSHPASS SSH_OPTS

set -euo pipefail

BENCH_FLAG_DEFAULT='FLAG{======RamiGPTi=====}'
BENCH_FLAG="${BENCH_FLAG:-$BENCH_FLAG_DEFAULT}"
BENCH_TIMEOUT="${BENCH_TIMEOUT:-45}"
BENCH_USER="${BENCH_USER:-lowpriv}"
BENCH_PASS="${BENCH_PASSWORD:-${BENCH_PASS:-password}}"

if [[ -z "${BENCH_HOST:-}" || -z "${BENCH_PORT:-}" ]]; then
  echo "BENCH_HOST and BENCH_PORT are required" >&2
  exit 1
fi

if ! command -v sshpass >/dev/null 2>&1; then
  echo "sshpass is required (brew install sshpass / apt install sshpass)" >&2
  exit 1
fi

SSH_BASE=(
  sshpass -p "${BENCH_PASS}"
  ssh
  -4
  -n
  -o StrictHostKeyChecking=no
  -o UserKnownHostsFile=/dev/null
  -o PreferredAuthentications=password
  -o PubkeyAuthentication=no
  -o ConnectTimeout=10
  -o LogLevel=ERROR
  -p "${BENCH_PORT}"
  "${BENCH_USER}@${BENCH_HOST}"
)

# Run a remote command; prints stdout+stderr. Exit code of remote cmd is returned.
ssh_run() {
  local remote_cmd="$1"
  "${SSH_BASE[@]}" -- "bash -lc $(printf '%q' "${remote_cmd}")"
}

# Success if captured output contains the flag or uid=0(root).
assert_root_output() {
  local out="$1"
  if grep -Fq "${BENCH_FLAG}" <<<"${out}"; then
    echo "OK: flag found"
    return 0
  fi
  if grep -Eq 'uid=0\(root\)' <<<"${out}"; then
    echo "OK: uid=0(root)"
    return 0
  fi
  echo "FAIL: no flag / root uid in output" >&2
  echo "----- output -----" >&2
  echo "${out}" >&2
  return 1
}

# Poll remote path for flag contents (crontab / importer).
wait_for_remote_file() {
  local path="$1"
  local seconds="${2:-90}"
  local i
  for ((i = 0; i < seconds; i++)); do
    if out="$(ssh_run "test -r '${path}' && cat '${path}'" 2>/dev/null || true)"; then
      if grep -Fq "${BENCH_FLAG}" <<<"${out}"; then
        echo "${out}"
        return 0
      fi
    fi
    sleep 1
  done
  return 1
}
