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

  # Form: cap-dac-read:python3
  cap-dac-read:*)
    name="${MISCONFIG#cap-dac-read:}"
    bin="$(resolve_bin "${name}")"
    setcap 'cap_dac_read_search+ep' "${bin}"
    getcap "${bin}" || true
    echo "[bench] cap_dac_read_search+ep on ${bin}"
    ;;

  # Form: cap-chown:python3
  cap-chown:*)
    name="${MISCONFIG#cap-chown:}"
    bin="$(resolve_bin "${name}")"
    # Path walk into /root requires traverse; CAP_CHOWN alone does not grant it.
    chmod 755 /root
    setcap 'cap_chown+ep' "${bin}"
    getcap "${bin}" || true
    echo "[bench] cap_chown+ep on ${bin} (/root traversable)"
    ;;

  # Form: cap-dac-override:python3
  cap-dac-override:*)
    name="${MISCONFIG#cap-dac-override:}"
    bin="$(resolve_bin "${name}")"
    setcap 'cap_dac_override+ep' "${bin}"
    getcap "${bin}" || true
    echo "[bench] cap_dac_override+ep on ${bin}"
    ;;

  # Form: cap-fowner:python3
  cap-fowner:*)
    name="${MISCONFIG#cap-fowner:}"
    bin="$(resolve_bin "${name}")"
    chmod 755 /root
    setcap 'cap_fowner+ep' "${bin}"
    getcap "${bin}" || true
    echo "[bench] cap_fowner+ep on ${bin} (/root traversable)"
    ;;

  # Form: cap-fsetid:python3 — root-owned world-writable binary; fsetid+fowner set SUID bash
  cap-fsetid:*)
    name="${MISCONFIG#cap-fsetid:}"
    bin="$(resolve_bin "${name}")"
    mkdir -p /opt/bench
    cp -a /bin/bash /opt/bench/fsetid-bin
    chown root:root /opt/bench/fsetid-bin
    chmod 777 /opt/bench/fsetid-bin
    setcap 'cap_fsetid,cap_fowner+ep' "${bin}"
    getcap "${bin}" || true
    echo "[bench] cap_fsetid,cap_fowner+ep on ${bin} + /opt/bench/fsetid-bin"
    ;;

  # ----- Full / group / writable-script sudo -----
  sudo-all)
    write_sudoers_dropin "all" "lowpriv ALL=(ALL) NOPASSWD: ALL"
    echo "[bench] sudo NOPASSWD: ALL"
    ;;

  sudo-group)
    groupadd -f benchsudo
    usermod -aG benchsudo lowpriv
    write_sudoers_dropin "group" "%benchsudo ALL=(ALL) NOPASSWD: /usr/bin/env"
    echo "[bench] group benchsudo NOPASSWD env"
    ;;

  sudo-writable-script)
    mkdir -p /opt/bench
    printf '%s\n' '#!/bin/sh' 'cat /root/flag.txt' > /opt/bench/root.sh
    chmod 777 /opt/bench/root.sh
    write_sudoers_dropin "writable-script" "lowpriv ALL=(ALL) NOPASSWD: /opt/bench/root.sh"
    echo "[bench] sudo NOPASSWD writable /opt/bench/root.sh"
    ;;

  sudo-pythonpath)
    mkdir -p /home/lowpriv/pyhijack
    chmod 777 /home/lowpriv/pyhijack
    chown lowpriv:lowpriv /home/lowpriv/pyhijack
    write_sudoers_dropin "pythonpath" "$(cat <<EOF
Defaults env_keep += "PYTHONPATH"
lowpriv ALL=(ALL) NOPASSWD: /usr/bin/python3
EOF
)"
    echo "[bench] sudo env_keep PYTHONPATH + NOPASSWD python3"
    ;;

  sudo-ld-library-path)
    mkdir -p /home/lowpriv/ldlib /opt/bench
    chmod 777 /home/lowpriv/ldlib
    chown lowpriv:lowpriv /home/lowpriv/ldlib
    cat >/opt/bench/ldvictim.c <<'EOF'
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
int main(void) {
  const char *base = getenv("LD_LIBRARY_PATH");
  if (!base || !*base) return 0;
  char path[512];
  snprintf(path, sizeof path, "%s/libpayload.so", base);
  (void)dlopen(path, RTLD_NOW);
  return 0;
}
EOF
    gcc -o /opt/bench/ldvictim /opt/bench/ldvictim.c -ldl
    chmod 755 /opt/bench/ldvictim
    write_sudoers_dropin "ldlibrarypath" "$(cat <<EOF
Defaults env_keep += "LD_LIBRARY_PATH"
lowpriv ALL=(ALL) NOPASSWD: /opt/bench/ldvictim
EOF
)"
    echo "[bench] sudo env_keep LD_LIBRARY_PATH + NOPASSWD /opt/bench/ldvictim"
    ;;

  sudo-bash-env)
    mkdir -p /home/lowpriv/bash_env
    chmod 777 /home/lowpriv/bash_env
    chown lowpriv:lowpriv /home/lowpriv/bash_env
    write_sudoers_dropin "bash_env" "$(cat <<EOF
Defaults env_keep += "BASH_ENV"
lowpriv ALL=(ALL) NOPASSWD: /bin/bash
EOF
)"
    echo "[bench] sudo env_keep BASH_ENV + NOPASSWD bash"
    ;;

  sudo-perl5lib)
    mkdir -p /home/lowpriv/perlhijack
    chmod 777 /home/lowpriv/perlhijack
    chown lowpriv:lowpriv /home/lowpriv/perlhijack
    write_sudoers_dropin "perl5lib" "$(cat <<EOF
Defaults env_keep += "PERL5LIB"
lowpriv ALL=(ALL) NOPASSWD: /usr/bin/perl
EOF
)"
    echo "[bench] sudo env_keep PERL5LIB + NOPASSWD perl"
    ;;

  sudo-rubylib)
    mkdir -p /home/lowpriv/rubyhijack
    chmod 777 /home/lowpriv/rubyhijack
    chown lowpriv:lowpriv /home/lowpriv/rubyhijack
    write_sudoers_dropin "rubylib" "$(cat <<EOF
Defaults env_keep += "RUBYLIB"
lowpriv ALL=(ALL) NOPASSWD: /usr/bin/ruby
EOF
)"
    echo "[bench] sudo env_keep RUBYLIB + NOPASSWD ruby"
    ;;

  sudo-mv)
    mkdir -p /opt/bench
    chmod 777 /opt/bench
    printf '%s\n' '#!/bin/sh' 'exit 0' > /opt/bench/mv-hook.sh
    chmod 755 /opt/bench/mv-hook.sh
    write_sudoers_dropin "mv" "lowpriv ALL=(ALL) NOPASSWD: /bin/mv"
    (
      while true; do
        /opt/bench/mv-hook.sh >/dev/null 2>&1 || true
        sleep 3
      done
    ) &
    echo "[bench] sudo NOPASSWD mv + writable /opt/bench/mv-hook.sh (+ poller)"
    ;;

  sudo-noauth)
    write_sudoers_dropin "noauth" "$(cat <<EOF
Defaults:lowpriv !authenticate
lowpriv ALL=(ALL) ALL
EOF
)"
    echo "[bench] Defaults !authenticate for lowpriv"
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

  writable:shadow)
    chmod 666 /etc/shadow
    echo "[bench] world-writable /etc/shadow"
    ;;

  writable:sudoers)
    # Modern sudo rejects non-root / world-writable sudoers files and often
    # skips world-writable includedirs. Lab: world-writable pending file that a
    # root poller validates and installs into /etc/sudoers.d/.
    mkdir -p /opt/bench /etc/sudoers.d
    printf '%s\n' '# write a valid sudoers rule here' > /opt/bench/sudoers.pending
    chmod 666 /opt/bench/sudoers.pending
    write_sudoers_dropin "00-baseline" "lowpriv ALL=(root) NOPASSWD: /usr/bin/true"
    (
      while true; do
        if [ -s /opt/bench/sudoers.pending ] && \
           visudo -cf /opt/bench/sudoers.pending >/dev/null 2>&1; then
          cp /opt/bench/sudoers.pending /etc/sudoers.d/99-pending
          chown root:root /etc/sudoers.d/99-pending
          chmod 440 /etc/sudoers.d/99-pending
        fi
        sleep 1
      done
    ) &
    echo "[bench] writable /opt/bench/sudoers.pending → /etc/sudoers.d (+ poller)"
    ;;

  writable:root-ssh)
    # World-writable authorized_keys; StrictModes would reject mode 666 / open dirs,
    # so disable it for this lab (common CTF tradeoff).
    mkdir -p /root/.ssh
    touch /root/.ssh/authorized_keys
    chmod 755 /root
    chmod 755 /root/.ssh
    chmod 666 /root/.ssh/authorized_keys
    chown root:root /root/.ssh /root/.ssh/authorized_keys
    if grep -qE '^#?StrictModes[[:space:]]+' /etc/ssh/sshd_config; then
      sed -i -E 's/^#?StrictModes[[:space:]].*/StrictModes no/' /etc/ssh/sshd_config
    else
      echo 'StrictModes no' >> /etc/ssh/sshd_config
    fi
    echo "[bench] world-writable authorized_keys + StrictModes no"
    ;;

  writable:lib)
    mkdir -p /usr/local/lib/benchhijack
    chmod 777 /usr/local/lib/benchhijack
    (
      while true; do
        python3 -c "import ctypes; ctypes.CDLL('/usr/local/lib/benchhijack/payload.so')" 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "[bench] writable /usr/local/lib/benchhijack (+ root CDLL poller)"
    ;;

  writable:ld-so-preload)
    touch /etc/ld.so.preload
    chmod 666 /etc/ld.so.preload
    (
      while true; do
        # Must be dynamically linked so ld.so.preload is consulted (/bin/true may be static).
        /usr/bin/id >/dev/null 2>&1 || true
        sleep 3
      done
    ) &
    echo "[bench] world-writable /etc/ld.so.preload (+ root /usr/bin/id poller)"
    ;;

  writable:cron-ref)
    # /etc/crontab is readable; it references a world-writable script (cron skips
    # insecure crontab files themselves — indirection stays realistic).
    mkdir -p /opt/bench
    printf '%s\n' '#!/bin/sh' 'exit 0' > /opt/bench/cronroot.sh
    chmod 777 /opt/bench/cronroot.sh
    printf '%s\n' '* * * * * root /opt/bench/cronroot.sh' >> /etc/crontab
    chmod 644 /etc/crontab
    if command -v cron >/dev/null 2>&1; then
      cron || true
    elif command -v crond >/dev/null 2>&1; then
      crond || true
    fi
    (
      while true; do
        /opt/bench/cronroot.sh >/dev/null 2>&1 || true
        sleep 3
      done
    ) &
    echo "[bench] /etc/crontab → writable /opt/bench/cronroot.sh (+ poller)"
    ;;

  writable:exports)
    touch /etc/exports
    printf '%s\n' '/tmp *(rw,sync,root_squash)' > /etc/exports
    chmod 666 /etc/exports
    echo "[bench] world-writable /etc/exports"
    ;;

  writable:profile)
    mkdir -p /etc/profile.d
    printf '%s\n' '# bench profile hook' > /etc/profile.d/bench-hook.sh
    chmod 777 /etc/profile.d/bench-hook.sh
    (
      while true; do
        bash -c 'source /etc/profile.d/bench-hook.sh' 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "[bench] writable /etc/profile.d/bench-hook.sh (+ root source poller)"
    ;;

  writable:bashrc)
    chmod 755 /root
    touch /root/.bashrc
    chmod 666 /root/.bashrc
    chown root:root /root/.bashrc
    (
      while true; do
        bash --noprofile --norc -c 'source /root/.bashrc' 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "[bench] writable /root/.bashrc (+ root source poller)"
    ;;

  suid-writable)
    mkdir -p /opt/bench
    bin="$(resolve_bin find)"
    cp -a "${bin}" /opt/bench/suidbin
    chmod 6777 /opt/bench/suidbin
    # Root poller: on nosuid mounts SUID is ignored; executing the replaced
    # binary as root still validates the writable-primitive path.
    (
      while true; do
        /opt/bench/suidbin >/dev/null 2>&1 || true
        sleep 1
      done
    ) &
    echo "[bench] writable SUID binary at /opt/bench/suidbin (+ root executor)"
    ;;

  cred-root-key)
    mkdir -p /root/.ssh /home/lowpriv
    rm -f /home/lowpriv/root_id_rsa /home/lowpriv/root_id_rsa.pub
    ssh-keygen -t rsa -b 2048 -f /home/lowpriv/root_id_rsa -N '' -q
    mkdir -p /root/.ssh
    cat /home/lowpriv/root_id_rsa.pub > /root/.ssh/authorized_keys
    chmod 700 /root/.ssh
    chmod 600 /root/.ssh/authorized_keys
    # World-readable so lowpriv can copy; clients should chmod 600 a private copy.
    chmod 644 /home/lowpriv/root_id_rsa /home/lowpriv/root_id_rsa.pub
    chown lowpriv:lowpriv /home/lowpriv/root_id_rsa /home/lowpriv/root_id_rsa.pub
    echo "[bench] world-readable root SSH key at /home/lowpriv/root_id_rsa"
    ;;

  # ----- PATH hijack -----
  path-hijack)
    mkdir -p /opt/pathhijack
    chmod 777 /opt/pathhijack
    (
      while true; do
        PATH="/opt/pathhijack:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
          runme >/dev/null 2>&1 || true
        sleep 3
      done
    ) &
    echo "[bench] root poller runs relative 'runme' with PATH=/opt/pathhijack first"
    ;;

  # ----- Credentials -----
  cred-cleartext)
    printf '%s\n' 'root_password=password' > /home/lowpriv/credentials.txt
    chmod 644 /home/lowpriv/credentials.txt
    chown lowpriv:lowpriv /home/lowpriv/credentials.txt
    echo "[bench] cleartext root password in /home/lowpriv/credentials.txt"
    ;;

  cred-history)
    printf '%s\n' \
      'su -' \
      '# root password is: password' \
      'echo password | su -c id' \
      > /home/lowpriv/.bash_history
    chown lowpriv:lowpriv /home/lowpriv/.bash_history
    chmod 644 /home/lowpriv/.bash_history
    echo "[bench] root password leaked in .bash_history"
    ;;

  cred-ansible)
    mkdir -p /home/lowpriv/.ansible /opt/ansible
    printf '%s\n' 'password' > /home/lowpriv/.ansible/vault_pass.txt
    printf '%s\n' \
      'ansible_user: root' \
      'ansible_ssh_pass: password' \
      'ansible_become_pass: password' \
      > /opt/ansible/group_vars_all.yml
    chmod 644 /home/lowpriv/.ansible/vault_pass.txt /opt/ansible/group_vars_all.yml
    chown -R lowpriv:lowpriv /home/lowpriv/.ansible
    echo "[bench] ansible vault pass + group_vars secrets (root password)"
    ;;

  cred-adm-log)
    groupadd -f adm
    usermod -aG adm lowpriv
    mkdir -p /var/log
    printf '%s\n' \
      'Jul 15 12:00:00 bench sudo: lowpriv : TTY=pts/0 ; PWD=/home/lowpriv ; USER=root ; COMMAND=/bin/bash' \
      'Jul 15 12:00:01 bench NOTE: root password for break-glass is: password' \
      > /var/log/bench-secure.log
    chown root:adm /var/log/bench-secure.log
    chmod 640 /var/log/bench-secure.log
    echo "[bench] lowpriv in adm; root password in /var/log/bench-secure.log"
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

  python-cwd)
    # Root job cds into a lowpriv-writable directory (cwd is early on sys.path).
    mkdir -p /home/lowpriv/cwd_hijack
    chmod 777 /home/lowpriv/cwd_hijack
    chown lowpriv:lowpriv /home/lowpriv/cwd_hijack
    (
      while true; do
        (cd /home/lowpriv/cwd_hijack && python3 -c 'import runner' 2>/dev/null) || true
        sleep 3
      done
    ) &
    echo "[bench] root python cwd=/home/lowpriv/cwd_hijack (+ importer)"
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
