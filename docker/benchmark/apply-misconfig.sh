#!/bin/bash
# Apply an intentional misconfig profile chosen by compose (MISCONFIG=…).
# Profiles are idempotent-ish: containers are typically --force-recreate.
set -euo pipefail

MISCONFIG="${MISCONFIG:-}"

if [[ -z "${MISCONFIG}" ]]; then
  echo "[bench] MISCONFIG empty — clean baseline (no intentional privilege path)"
  exit 0
fi

echo "[bench] applying MISCONFIG=${MISCONFIG}"

write_sudoers_dropin() {
  local name="$1"
  local body="$2"
  local path="/etc/sudoers.d/${name}"
  printf '%s\n' "${body}" >"${path}"
  chmod 440 "${path}"
  visudo -cf "${path}"
}

resolve_bin() {
  local name="$1"
  local path
  path="$(command -v "${name}" || true)"
  if [[ -z "${path}" || ! -x "${path}" ]]; then
    echo "[bench] binary not found/executable: ${name}" >&2
    exit 1
  fi
  # Prefer real path (python3 may be a symlink)
  readlink -f "${path}" 2>/dev/null || echo "${path}"
}

case "${MISCONFIG}" in
  # ----- Sudo NOPASSWD (GTFOBins-style) -----
  # Form: sudo:/usr/bin/vim   OR   sudo:vim
  sudo:*)
    raw="${MISCONFIG#sudo:}"
    if [[ "${raw}" == /* ]]; then
      bin="${raw}"
    else
      bin="$(resolve_bin "${raw}")"
    fi
    test -x "${bin}" || { echo "[bench] missing ${bin}" >&2; exit 1; }
    write_sudoers_dropin "nopasswd" "lowpriv ALL=(ALL) NOPASSWD: ${bin}"
    echo "[bench] sudo NOPASSWD for ${bin}"
    ;;

  # Sudo + LD_PRELOAD kept (BeRoot: env_keep LD_PRELOAD)
  # Form: sudo-ld-preload:/usr/bin/find
  sudo-ld-preload:*)
    raw="${MISCONFIG#sudo-ld-preload:}"
    if [[ "${raw}" == /* ]]; then
      bin="${raw}"
    else
      bin="$(resolve_bin "${raw}")"
    fi
    write_sudoers_dropin "ldpreload" "$(cat <<EOF
Defaults env_keep += "LD_PRELOAD"
lowpriv ALL=(ALL) NOPASSWD: ${bin}
EOF
)"
    echo "[bench] sudo LD_PRELOAD keep + NOPASSWD ${bin}"
    ;;

  # ----- SUID -----
  # Form: suid:find
  suid:*)
    name="${MISCONFIG#suid:}"
    bin="$(resolve_bin "${name}")"
    chmod u+s "${bin}"
    # Ensure world-executable so lowpriv can invoke
    chmod a+rx "${bin}" || true
    echo "[bench] SUID set on ${bin}"
    ;;

  # ----- Capabilities -----
  # Form: cap-setuid:python3
  cap-setuid:*)
    name="${MISCONFIG#cap-setuid:}"
    bin="$(resolve_bin "${name}")"
    setcap 'cap_setuid+ep' "${bin}"
    getcap "${bin}" || true
    echo "[bench] cap_setuid+ep on ${bin}"
    ;;

  # ----- Writable sensitive paths -----
  writable:crontab)
    # Modern cron skips world-writable crontab/cron.d files. Instead: a root
    # cron.d entry runs a world-writable script (BeRoot-interesting writable path).
    mkdir -p /opt/bench
    printf '%s\n' '#!/bin/sh' 'exit 0' > /opt/bench/job.sh
    chmod 777 /opt/bench/job.sh
    printf '%s\n' '* * * * * root /opt/bench/job.sh' > /etc/cron.d/bench-job
    chmod 644 /etc/cron.d/bench-job
    if command -v cron >/dev/null 2>&1; then
      cron || true
    elif command -v crond >/dev/null 2>&1; then
      crond || true
    fi
    # Fast path for verify (cron is minute-granular).
    (
      while true; do
        /opt/bench/job.sh >/dev/null 2>&1 || true
        sleep 3
      done
    ) &
    echo "[bench] writable /opt/bench/job.sh invoked by root cron (+ poller)"
    ;;

  writable:passwd)
    chmod 666 /etc/passwd
    echo "[bench] world-writable /etc/passwd"
    ;;

  # ----- Python library hijack -----
  python-hijack)
    # Prefer a non-cwd sys.path entry that BeRoot flags when writable.
    target=""
    while IFS= read -r line; do
      if [[ -n "${line}" && -d "${line}" && "${line}" != "." ]]; then
        target="${line}"
        break
      fi
    done < <(python3 - <<'PY'
import sys
for p in sys.path:
    if p and p != ".":
        print(p)
PY
)
    if [[ -z "${target}" ]]; then
      target="/usr/lib/python3/dist-packages"
      mkdir -p "${target}"
    fi
    chmod 777 "${target}"
    # Root periodically imports bench_hijack so a planted module escalates.
    printf '%s\n' '* * * * * root python3 -c "import bench_hijack" 2>/dev/null' \
      > /etc/cron.d/bench-hijack-trigger
    chmod 644 /etc/cron.d/bench-hijack-trigger
    if command -v cron >/dev/null 2>&1; then
      cron || true
    fi
    # Fast path for verify scripts (cron is ~1min).
    (
      while true; do
        python3 -c "import bench_hijack" 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "${target}" > /home/lowpriv/.bench_python_hijack_path
    chown lowpriv:lowpriv /home/lowpriv/.bench_python_hijack_path
    echo "[bench] world-writable python path: ${target} (+ root importer)"
    ;;

  # ----- NFS exports (BeRoot detect-only unless host NFS is used) -----
  nfs-exports)
    printf '%s\n' '/tmp *(rw,sync,no_root_squash)' > /etc/exports
    chmod 644 /etc/exports
    echo "[bench] planted /etc/exports with no_root_squash"
    ;;

  *)
    echo "[bench] unknown MISCONFIG=${MISCONFIG}" >&2
    exit 1
    ;;
esac
