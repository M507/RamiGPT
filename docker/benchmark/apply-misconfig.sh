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
  echo "${path}"
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
    bin="$(readlink -f "${bin}")"
    setcap 'cap_setuid+ep' "${bin}"
    getcap "${bin}" || true
    echo "[bench] cap_setuid+ep on ${bin}"
    ;;

  # Form: cap-dac-read:python3
  cap-dac-read:*)
    name="${MISCONFIG#cap-dac-read:}"
    bin="$(resolve_bin "${name}")"
    bin="$(readlink -f "${bin}")"
    setcap 'cap_dac_read_search+ep' "${bin}"
    getcap "${bin}" || true
    echo "[bench] cap_dac_read_search+ep on ${bin}"
    ;;

  # Form: cap-chown:python3
  cap-chown:*)
    name="${MISCONFIG#cap-chown:}"
    bin="$(resolve_bin "${name}")"
    bin="$(readlink -f "${bin}")"
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
    bin="$(readlink -f "${bin}")"
    setcap 'cap_dac_override+ep' "${bin}"
    getcap "${bin}" || true
    echo "[bench] cap_dac_override+ep on ${bin}"
    ;;

  # Form: cap-fowner:python3
  cap-fowner:*)
    name="${MISCONFIG#cap-fowner:}"
    bin="$(resolve_bin "${name}")"
    bin="$(readlink -f "${bin}")"
    chmod 755 /root
    setcap 'cap_fowner+ep' "${bin}"
    getcap "${bin}" || true
    echo "[bench] cap_fowner+ep on ${bin} (/root traversable)"
    ;;

  # Form: cap-fsetid:python3 — root-owned world-writable binary; fsetid+fowner set SUID bash
  cap-fsetid:*)
    name="${MISCONFIG#cap-fsetid:}"
    bin="$(resolve_bin "${name}")"
    bin="$(readlink -f "${bin}")"
    mkdir -p /opt/bench
    cp -a /bin/bash /opt/bench/fsetid-bin
    chown root:root /opt/bench/fsetid-bin
    chmod 777 /opt/bench/fsetid-bin
    setcap 'cap_fsetid,cap_fowner+ep' "${bin}"
    getcap "${bin}" || true
    echo "[bench] cap_fsetid,cap_fowner+ep on ${bin} + /opt/bench/fsetid-bin"
    ;;

  sudo-composer)
    mkdir -p /home/lowpriv/composerproj
    chown lowpriv:lowpriv /home/lowpriv/composerproj
    write_sudoers_dropin "composer" "lowpriv ALL=(ALL) NOPASSWD: /usr/bin/composer"
    echo "[bench] sudo NOPASSWD composer (script hooks run as root)"
    ;;

  sudo-pip)
    mkdir -p /home/lowpriv/pipproj
    chown lowpriv:lowpriv /home/lowpriv/pipproj
    write_sudoers_dropin "pip" "lowpriv ALL=(ALL) NOPASSWD: /usr/bin/pip3"
    echo "[bench] sudo NOPASSWD pip3 (setup.py install hooks run as root)"
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

  # ----- Mid tier: custom SUID / SGID / cron / credentials -----
  suid-path-hijack)
    mkdir -p /opt/bench /opt/pathhijack-suid
    chmod 777 /opt/pathhijack-suid
    cat >/opt/bench/suid_path.c <<'EOF'
#include <stdlib.h>
int main(void) {
  system("benchhelper");
  return 0;
}
EOF
    gcc -o /opt/bench/suid_path /opt/bench/suid_path.c
    chown root:root /opt/bench/suid_path
    chmod u+s,a+rx /opt/bench/suid_path
    # nosuid mounts ignore the SUID bit — root poller executes the binary.
    (
      while true; do
        PATH="/opt/pathhijack-suid:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
          /opt/bench/suid_path >/dev/null 2>&1 || true
        sleep 3
      done
    ) &
    echo "[bench] SUID /opt/bench/suid_path → system(\"benchhelper\") (+ root PATH poller)"
    ;;

  suid-writable-exec)
    mkdir -p /opt/bench
    printf '%s\n' '#!/bin/sh' 'exit 0' > /opt/bench/helper
    chmod 777 /opt/bench/helper
    cat >/opt/bench/suid_exec.c <<'EOF'
#include <unistd.h>
int main(void) {
  execl("/opt/bench/helper", "helper", (char *)0);
  return 1;
}
EOF
    gcc -o /opt/bench/suid_exec /opt/bench/suid_exec.c
    chown root:root /opt/bench/suid_exec
    chmod u+s,a+rx /opt/bench/suid_exec
    (
      while true; do
        /opt/bench/suid_exec >/dev/null 2>&1 || true
        sleep 3
      done
    ) &
    echo "[bench] SUID /opt/bench/suid_exec → execl /opt/bench/helper (+ root poller)"
    ;;

  wildcard-cron)
    mkdir -p /opt/bench/wildcard
    chown lowpriv:lowpriv /opt/bench/wildcard
    chmod 755 /opt/bench/wildcard
    printf '%s\n' \
      '* * * * * root /bin/bash -c "for f in /opt/bench/wildcard/*; do [ -x \"\$f\" ] && \"\$f\"; done"' \
      > /etc/cron.d/bench-wildcard
    chmod 644 /etc/cron.d/bench-wildcard
    if command -v cron >/dev/null 2>&1; then
      cron || true
    fi
    (
      while true; do
        /bin/bash -c 'for f in /opt/bench/wildcard/*; do [ -x "$f" ] && "$f"; done' 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "[bench] root wildcard cron on /opt/bench/wildcard/* (+ poller)"
    ;;

  cred-shadow-read)
    chmod 644 /etc/shadow
    echo "[bench] world-readable /etc/shadow (root password unchanged: password)"
    ;;

  sgid-secret)
    groupadd -f benchsecret
    mkdir -p /opt/bench /var/bench
    cat >/opt/bench/sgidread.c <<'EOF'
#include <stdio.h>
int main(int argc, char **argv) {
  FILE *f;
  char buf[512];
  if (argc < 2) return 1;
  f = fopen(argv[1], "r");
  if (!f) return 1;
  while (fgets(buf, sizeof buf, f)) fputs(buf, stdout);
  fclose(f);
  return 0;
}
EOF
    gcc -o /opt/bench/sgidcat /opt/bench/sgidread.c
    chown root:benchsecret /opt/bench/sgidcat
    chmod 2755 /opt/bench/sgidcat
    cp /root/flag.txt /var/bench/flagcopy
    chown root:benchsecret /var/bench/flagcopy
    chmod 640 /var/bench/flagcopy
    echo "[bench] SGID /opt/bench/sgidcat (group benchsecret) + group-readable flag"
    ;;

  sudo-runas)
    useradd -m -s /bin/bash deploy 2>/dev/null || true
    echo 'deploy:password' | chpasswd
    printf '%s\n' 'root_password=password' > /home/deploy/credentials.txt
    chmod 644 /home/deploy/credentials.txt
    chown deploy:deploy /home/deploy/credentials.txt
    write_sudoers_dropin "runas" "lowpriv ALL=(deploy) NOPASSWD: ALL"
    echo "[bench] sudo runas deploy + readable deploy credentials"
    ;;

  writable:ld-so-conf)
    mkdir -p /etc/ld.so.conf.d /usr/local/lib/benchevil /opt/bench
    chmod 777 /usr/local/lib/benchevil
    touch /etc/ld.so.conf.d/bench.conf
    chmod 666 /etc/ld.so.conf.d/bench.conf
    cat >/opt/bench/ldconf_victim.c <<'EOF'
#include <dlfcn.h>
int main(void) {
  (void)dlopen("libevil.so", RTLD_NOW);
  return 0;
}
EOF
    gcc -o /opt/bench/ldconf_victim /opt/bench/ldconf_victim.c -ldl
    chmod 755 /opt/bench/ldconf_victim
    (
      while true; do
        ldconfig 2>/dev/null || true
        /opt/bench/ldconf_victim >/dev/null 2>&1 || true
        sleep 3
      done
    ) &
    echo "[bench] writable ld.so.conf.d + /opt/bench/ldconf_victim dlopen poller"
    ;;

  sudo-wildcard-tar)
    mkdir -p /opt/bench/tarwild
    chown lowpriv:lowpriv /opt/bench/tarwild
    chmod 755 /opt/bench/tarwild
    cat >/opt/bench/backup.sh <<'EOF'
#!/bin/sh
cd /opt/bench/tarwild && tar -cf /tmp/backup.tar *
EOF
    chmod 755 /opt/bench/backup.sh
    write_sudoers_dropin "wildtar" "lowpriv ALL=(ALL) NOPASSWD: /opt/bench/backup.sh"
    echo "[bench] sudo NOPASSWD backup.sh with tar wildcard in lowpriv dir"
    ;;

  logrotate-writable)
    mkdir -p /var/log/bench /etc/logrotate.d /opt/bench
    printf '%s\n' 'bench log' > /var/log/bench/app.log
    cat >/etc/logrotate.d/bench <<'EOF'
/var/log/bench/*.log {
    size 1
    rotate 1
    missingok
    copytruncate
    postrotate
        /opt/bench/logrotate-hook.sh
    endscript
}
EOF
    printf '%s\n' '#!/bin/sh' 'exit 0' > /opt/bench/logrotate-hook.sh
    chmod 777 /opt/bench/logrotate-hook.sh
    (
      while true; do
        logrotate -f /etc/logrotate.d/bench 2>/dev/null || true
        sleep 5
      done
    ) &
    echo "[bench] writable /opt/bench/logrotate-hook.sh (+ root logrotate poller)"
    ;;

  cred-core-dump)
    mkdir -p /var/crash /home/lowpriv
    printf '%s\n' \
      'Core dump from /usr/sbin/benchd (root)' \
      'recover password: password' \
      "FLAG{======RamiGPTi=====}" \
      > /var/crash/bench-app.core
    chmod 644 /var/crash/bench-app.core
    chown root:root /var/crash/bench-app.core
    echo "[bench] world-readable fake core dump with root password"
    ;;

  suid-dlopen)
    mkdir -p /opt/bench/evil
    chmod 777 /opt/bench/evil
    cat >/opt/bench/suid_dlopen.c <<'EOF'
#include <dlfcn.h>
int main(void) {
  (void)dlopen("/opt/bench/evil/libpayload.so", RTLD_NOW);
  return 0;
}
EOF
    gcc -o /opt/bench/suid_dlopen /opt/bench/suid_dlopen.c -ldl
    chown root:root /opt/bench/suid_dlopen
    chmod u+s,a+rx /opt/bench/suid_dlopen
    (
      while true; do
        /opt/bench/suid_dlopen >/dev/null 2>&1 || true
        sleep 3
      done
    ) &
    echo "[bench] SUID dlopen victim + writable /opt/bench/evil (+ poller)"
    ;;

  writable:motd)
    mkdir -p /etc/update-motd.d
    printf '%s\n' '#!/bin/sh' '# bench motd hook' > /etc/update-motd.d/99-bench
    chmod 777 /etc/update-motd.d/99-bench
    (
      while true; do
        bash -c 'for f in /etc/update-motd.d/*; do [ -x "$f" ] && "$f"; done' 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "[bench] writable /etc/update-motd.d/99-bench (+ root run-parts poller)"
    ;;

  sudo-git-hook)
    mkdir -p /opt/bench/repo
    git init -b main /opt/bench/repo >/dev/null 2>&1 || git init /opt/bench/repo
    git -C /opt/bench/repo config user.email bench@local
    git -C /opt/bench/repo config user.name bench
    printf '%s\n' 'init' > /opt/bench/repo/README
    git -C /opt/bench/repo add README
    git -C /opt/bench/repo commit -m init >/dev/null 2>&1 || true
    chown -R lowpriv:lowpriv /opt/bench/repo
    chmod 777 /opt/bench/repo/.git/hooks
    write_sudoers_dropin "git" "lowpriv ALL=(ALL) NOPASSWD: /usr/bin/git"
    echo "[bench] sudo NOPASSWD git + writable hooks in /opt/bench/repo"
    ;;

  at-allow)
    mkdir -p /opt/bench
    touch /etc/at.allow
    printf '%s\n' 'root' > /etc/at.allow
    chmod 666 /etc/at.allow
    printf '%s\n' '#!/bin/sh' 'exit 0' > /opt/bench/atjob
    chmod 777 /opt/bench/atjob
    if command -v atd >/dev/null 2>&1; then
      atd || true
    fi
    (
      while true; do
        at -f /opt/bench/atjob now 2>/dev/null || true
        sleep 5
      done
    ) &
    echo "[bench] writable /etc/at.allow + root at -f /opt/bench/atjob poller"
    ;;

  ld-preload-script)
    mkdir -p /opt/bench
    chmod 777 /opt/bench
    printf '%s\n' '#!/bin/sh' 'export LD_PRELOAD=/opt/bench/preload.so' 'exec /usr/bin/id "$@"' > /opt/bench/rootwrap.sh
    chmod 777 /opt/bench/rootwrap.sh
    (
      while true; do
        /opt/bench/rootwrap.sh >/dev/null 2>&1 || true
        sleep 3
      done
    ) &
    echo "[bench] world-writable /opt/bench/rootwrap.sh sets LD_PRELOAD (+ poller)"
    ;;

  writable-cron-allow)
    mkdir -p /opt/bench
    touch /etc/cron.allow
    printf '%s\n' 'root' > /etc/cron.allow
    chmod 666 /etc/cron.allow
    printf '%s\n' '#!/bin/sh' 'exit 0' > /opt/bench/cronjob
    chmod 777 /opt/bench/cronjob
    printf '%s\n' '* * * * * root /opt/bench/cronjob' > /etc/cron.d/bench-cronjob
    chmod 644 /etc/cron.d/bench-cronjob
    if command -v cron >/dev/null 2>&1; then
      cron || true
    fi
    (
      while true; do
        /opt/bench/cronjob 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "[bench] writable /etc/cron.allow + root /opt/bench/cronjob poller"
    ;;

  sudo-gem)
    mkdir -p /home/lowpriv/gemproj
    chown lowpriv:lowpriv /home/lowpriv/gemproj
    write_sudoers_dropin "gem" "lowpriv ALL=(ALL) NOPASSWD: /usr/bin/gem"
    echo "[bench] sudo NOPASSWD gem install (extconf/post_install hooks run as root)"
    ;;

  rbash-escape)
    ln -sf /bin/bash /bin/rbash 2>/dev/null || true
    usermod -s /bin/rbash lowpriv
    mkdir -p /home/lowpriv/escape
    chown lowpriv:lowpriv /home/lowpriv/escape
    chmod 755 /home/lowpriv/escape
    (
      while true; do
        /bin/bash -c 'for f in /home/lowpriv/escape/*; do [ -x "$f" ] && "$f"; done' 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "[bench] rbash login shell + root poller on /home/lowpriv/escape/*"
    ;;

  sudo-npm)
    mkdir -p /home/lowpriv/npmproj
    chown lowpriv:lowpriv /home/lowpriv/npmproj
    write_sudoers_dropin "npm" "lowpriv ALL=(ALL) NOPASSWD: /usr/bin/npm"
    echo "[bench] sudo NOPASSWD npm (lifecycle scripts run as root)"
    ;;

  writable-init-d)
    cat >/etc/init.d/benchsvc <<'EOF'
#!/bin/sh
exit 0
EOF
    chmod 777 /etc/init.d/benchsvc
    (
      while true; do
        /bin/sh /etc/init.d/benchsvc 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "[bench] world-writable /etc/init.d/benchsvc (+ root poller)"
    ;;

  sudo-ps4)
    write_sudoers_dropin "ps4" "$(cat <<EOF
Defaults env_keep += "PS4"
lowpriv ALL=(ALL) NOPASSWD: /bin/bash
EOF
)"
    echo "[bench] sudo env_keep PS4 + NOPASSWD bash"
    ;;

  sudo-shelopts)
    write_sudoers_dropin "shelopts" "$(cat <<EOF
Defaults env_keep += "SHELLOPTS"
Defaults env_keep += "PS4"
lowpriv ALL=(ALL) NOPASSWD: /bin/bash
EOF
)"
    echo "[bench] sudo env_keep SHELLOPTS/PS4 + NOPASSWD bash"
    ;;

  sudo-nodepath)
    mkdir -p /home/lowpriv/nodehijack
    chmod 777 /home/lowpriv/nodehijack
    chown lowpriv:lowpriv /home/lowpriv/nodehijack
    write_sudoers_dropin "nodepath" "$(cat <<EOF
Defaults env_keep += "NODE_PATH"
lowpriv ALL=(ALL) NOPASSWD: /usr/bin/node
EOF
)"
    echo "[bench] sudo env_keep NODE_PATH + NOPASSWD node"
    ;;

  writable:cron-d)
    mkdir -p /opt/bench
    printf '%s\n' '* * * * * root /opt/bench/cron-d-job' > /etc/cron.d/bench-writable
    chmod 666 /etc/cron.d/bench-writable
    printf '%s\n' '#!/bin/sh' 'exit 0' > /opt/bench/cron-d-job
    chmod 777 /opt/bench/cron-d-job
    if command -v cron >/dev/null 2>&1; then cron || true; fi
    (
      while true; do
        /opt/bench/cron-d-job 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "[bench] writable /etc/cron.d/bench-writable + root job poller"
    ;;

  writable:crontab-system)
    mkdir -p /opt/bench
    cat >/etc/crontab <<'EOF'
SHELL=/bin/sh
PATH=/usr/bin:/bin
* * * * * root /opt/bench/system-cron-job
EOF
    chmod 666 /etc/crontab
    printf '%s\n' '#!/bin/sh' 'exit 0' > /opt/bench/system-cron-job
    chmod 777 /opt/bench/system-cron-job
    if command -v cron >/dev/null 2>&1; then cron || true; fi
    (
      while true; do
        /opt/bench/system-cron-job 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "[bench] writable /etc/crontab + root system-cron-job poller"
    ;;

  writable:anacrontab)
    mkdir -p /opt/bench
    touch /etc/anacrontab
    chmod 666 /etc/anacrontab
    printf '%s\n' '#!/bin/sh' 'exit 0' > /opt/bench/anacron-hook.sh
    chmod 777 /opt/bench/anacron-hook.sh
    (
      while true; do
        /opt/bench/anacron-hook.sh 2>/dev/null || true
        sleep 5
      done
    ) &
    echo "[bench] writable /etc/anacrontab + root anacron-hook poller"
    ;;

  writable:rc-local)
    cat >/etc/rc.local <<'EOF'
#!/bin/sh
exit 0
EOF
    chmod 777 /etc/rc.local
    (
      while true; do
        /bin/sh /etc/rc.local 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "[bench] world-writable /etc/rc.local (+ root poller)"
    ;;

  writable:sshd-config)
    mkdir -p /etc/ssh/sshd_config.d /opt/bench
    printf '%s\n' '# bench sshd drop-in' > /etc/ssh/sshd_config.d/99-bench.conf
    chmod 666 /etc/ssh/sshd_config.d/99-bench.conf
    printf '%s\n' '#!/bin/sh' 'exit 0' > /opt/bench/sshd-hook.sh
    chmod 777 /opt/bench/sshd-hook.sh
    (
      while true; do
        /opt/bench/sshd-hook.sh 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "[bench] writable sshd_config.d + /opt/bench/sshd-hook.sh poller"
    ;;

  writable:pam)
    mkdir -p /opt/bench
    printf '%s\n' 'auth optional pam_exec.so /opt/bench/pam-exec.sh' > /etc/pam.d/bench-hook
    chmod 666 /etc/pam.d/bench-hook
    printf '%s\n' '#!/bin/sh' 'exit 0' > /opt/bench/pam-exec.sh
    chmod 777 /opt/bench/pam-exec.sh
    (
      while true; do
        /opt/bench/pam-exec.sh 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "[bench] writable /etc/pam.d/bench-hook + pam_exec poller"
    ;;

  php-include-hijack)
    mkdir -p /opt/bench/phpinc /opt/bench
    chmod 777 /opt/bench/phpinc
    cat >/opt/bench/php-runner.php <<'EOF'
<?php
@include getenv("BENCH_PHP_INCLUDE") ?: "/opt/bench/phpinc/evil.php";
EOF
    chmod 755 /opt/bench/php-runner.php
    (
      while true; do
        BENCH_PHP_INCLUDE=/opt/bench/phpinc/evil.php php /opt/bench/php-runner.php >/dev/null 2>&1 || true
        sleep 3
      done
    ) &
    echo "[bench] root php include from writable /opt/bench/phpinc (+ poller)"
    ;;

  node-path-hijack)
    mkdir -p /opt/bench/nodeinc /opt/bench
    chmod 777 /opt/bench/nodeinc
    cat >/opt/bench/node-runner.js <<'EOF'
require("benchpwn");
EOF
    chmod 755 /opt/bench/node-runner.js
    (
      while true; do
        NODE_PATH=/opt/bench/nodeinc node /opt/bench/node-runner.js >/dev/null 2>&1 || true
        sleep 3
      done
    ) &
    echo "[bench] root node import from writable NODE_PATH (+ poller)"
    ;;

  root-tcp-service)
    mkdir -p /opt/bench
    cat >/opt/bench/rootd.py <<'EOF'
#!/usr/bin/env python3
import http.server, socketserver, subprocess, urllib.parse, os
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/run?"):
            q = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(q)
            cmd = params.get("cmd", [""])[0]
            out = subprocess.check_output(cmd, shell=True, text=True)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(out.encode())
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, *args):
        pass
os.chdir("/")
with socketserver.TCPServer(("127.0.0.1", 8877), H) as httpd:
    httpd.serve_forever()
EOF
    chmod 755 /opt/bench/rootd.py
    nohup python3 /opt/bench/rootd.py >/dev/null 2>&1 &
    echo "[bench] root HTTP on 127.0.0.1:8877 with shell exec"
    ;;

  writable:webroot)
    mkdir -p /var/www/bench
    chmod 777 /var/www/bench
    (
      while true; do
        for f in /var/www/bench/*.php; do
          [ -f "$f" ] && php "$f" >/dev/null 2>&1 || true
        done
        sleep 3
      done
    ) &
    echo "[bench] writable /var/www/bench + root php poller"
    ;;

  mysql-socket)
    mkdir -p /var/run/mysqld /var/lib/mysql /opt/bench
    chown -R mysql:mysql /var/lib/mysql /var/run/mysqld 2>/dev/null || true
    if [ ! -d /var/lib/mysql/mysql ]; then
      mariadb-install-db --user=mysql --datadir=/var/lib/mysql >/dev/null 2>&1 || \
        mysql_install_db --user=mysql --datadir=/var/lib/mysql >/dev/null 2>&1 || true
    fi
    mysqld --user=mysql --bind-address=127.0.0.1 --skip-networking=0 --datadir=/var/lib/mysql \
      --socket=/var/run/mysqld/mysqld.sock >/dev/null 2>&1 &
    for _ in $(seq 1 30); do
      [ -S /var/run/mysqld/mysqld.sock ] && break
      sleep 1
    done
    mysql -u root --socket=/var/run/mysqld/mysqld.sock -e \
      "ALTER USER 'root'@'localhost' IDENTIFIED VIA mysql_native_password USING PASSWORD(''); FLUSH PRIVILEGES;" \
      2>/dev/null || mysql -u root --socket=/var/run/mysqld/mysqld.sock -e "FLUSH PRIVILEGES;" 2>/dev/null || true
    cp /root/flag.txt /var/lib/mysql/flag.txt
    chown mysql:mysql /var/lib/mysql/flag.txt
    chmod 644 /var/lib/mysql/flag.txt
    echo "[bench] mariadb root socket + flag copy readable by mysql user"
    ;;

  sudo-backup)
    mkdir -p /opt/bench/backups
    chmod 777 /opt/bench/backups
    chown lowpriv:lowpriv /opt/bench/backups
    cat >/opt/bench/backup.sh <<'EOF'
#!/bin/sh
cd /opt/bench/backups && tar -czf /tmp/backup.tgz *
EOF
    chmod 755 /opt/bench/backup.sh
    write_sudoers_dropin "backup" "lowpriv ALL=(ALL) NOPASSWD: /opt/bench/backup.sh"
    echo "[bench] sudo NOPASSWD backup.sh with tar wildcard in backups dir"
    ;;

  writable:vpn-hook)
    mkdir -p /etc/openvpn/client /opt/bench
    printf '%s\n' '#!/bin/sh' 'exit 0' > /etc/openvpn/client/up.sh
    chmod 777 /etc/openvpn/client/up.sh
    (
      while true; do
        /etc/openvpn/client/up.sh 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "[bench] writable /etc/openvpn/client/up.sh (+ root poller)"
    ;;

  doas-nopass)
    cat >/etc/doas.conf <<'EOF'
permit nopass keepenv lowpriv as root
EOF
    chmod 600 /etc/doas.conf
    echo "[bench] doas permit nopass lowpriv as root"
    ;;

  sudo-strings)
    write_sudoers_dropin "strings" "lowpriv ALL=(ALL) NOPASSWD: /usr/bin/strings"
    echo "[bench] sudo NOPASSWD strings (read arbitrary files as root)"
    ;;

  cap-setfcap:*)
    name="${MISCONFIG#cap-setfcap:}"
    bin="$(resolve_bin "${name}")"
    bin="$(readlink -f "${bin}")"
    mkdir -p /opt/bench
    cp -a /bin/bash /opt/bench/setcap-bin
    chown root:root /opt/bench/setcap-bin
    chmod 777 /opt/bench/setcap-bin
    setcap 'cap_fsetid,cap_fowner+ep' "${bin}"
    getcap "${bin}" || true
    echo "[bench] cap_fsetid,cap_fowner+ep on ${bin} (setcap-class via chmod SUID)"
    ;;

  sudo-yarn)
    mkdir -p /home/lowpriv/yarnproj
    chown lowpriv:lowpriv /home/lowpriv/yarnproj
    write_sudoers_dropin "yarn" "lowpriv ALL=(ALL) NOPASSWD: /usr/local/bin/yarn"
    echo "[bench] sudo NOPASSWD yarn (lifecycle scripts run as root)"
    ;;

  cred-env-file)
    cat >/etc/environment <<'EOF'
PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ROOT_PASS=password
EOF
    chmod 644 /etc/environment
    echo "[bench] world-readable /etc/environment with root password hint"
    ;;

  sudo-ansible)
    mkdir -p /opt/bench/ansible
    chmod 777 /opt/bench/ansible
    write_sudoers_dropin "ansible" "lowpriv ALL=(ALL) NOPASSWD: /usr/bin/ansible-playbook"
    echo "[bench] sudo NOPASSWD ansible-playbook + writable /opt/bench/ansible"
    ;;

  sudo-xxd)
    write_sudoers_dropin "xxd" "lowpriv ALL=(ALL) NOPASSWD: /usr/bin/xxd"
    echo "[bench] sudo NOPASSWD xxd"
    ;;

  sudo-od)
    write_sudoers_dropin "od" "lowpriv ALL=(ALL) NOPASSWD: /usr/bin/od"
    echo "[bench] sudo NOPASSWD od"
    ;;

  sudo-perl-exec)
    write_sudoers_dropin "perl" "lowpriv ALL=(ALL) NOPASSWD: /usr/bin/perl"
    echo "[bench] sudo NOPASSWD perl -e exec"
    ;;

  writable:apache-config)
    mkdir -p /etc/apache2/conf-available /opt/bench
    printf '%s\n' '# bench apache hook' > /etc/apache2/conf-available/bench.conf
    chmod 666 /etc/apache2/conf-available/bench.conf
    printf '%s\n' '#!/bin/sh' 'exit 0' > /opt/bench/apache-hook.sh
    chmod 777 /opt/bench/apache-hook.sh
    (
      while true; do
        /opt/bench/apache-hook.sh 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "[bench] writable apache conf-available + root hook poller"
    ;;

  cred-backup-secrets)
    mkdir -p /var/backups
    printf '%s\n' 'root_password=password' 'db_pass=SuperSecret' > /var/backups/credentials.txt
    chmod 644 /var/backups/credentials.txt
    echo "[bench] world-readable /var/backups/credentials.txt"
    ;;

  writable:nginx-config)
    mkdir -p /etc/nginx/conf.d /opt/bench
    printf '%s\n' '# bench nginx hook' > /etc/nginx/conf.d/bench.conf
    chmod 666 /etc/nginx/conf.d/bench.conf
    printf '%s\n' '#!/bin/sh' 'exit 0' > /opt/bench/nginx-hook.sh
    chmod 777 /opt/bench/nginx-hook.sh
    (
      while true; do
        /opt/bench/nginx-hook.sh 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "[bench] writable nginx conf.d + root hook poller"
    ;;

  cred-netrc)
    cat >/home/lowpriv/.netrc <<'EOF'
machine localhost
login root
password password
EOF
    chmod 644 /home/lowpriv/.netrc
    chown lowpriv:lowpriv /home/lowpriv/.netrc
    echo "[bench] world-readable ~/.netrc with root password"
    ;;

  cred-git-config)
    cat >/home/lowpriv/.git-credentials <<'EOF'
https://root:password@127.0.0.1
EOF
    chmod 644 /home/lowpriv/.git-credentials
    chown lowpriv:lowpriv /home/lowpriv/.git-credentials
    echo "[bench] world-readable ~/.git-credentials with root password"
    ;;

  cred-mysql-cnf)
    cat >/home/lowpriv/.my.cnf <<'EOF'
[client]
user=root
password=password
EOF
    chmod 644 /home/lowpriv/.my.cnf
    chown lowpriv:lowpriv /home/lowpriv/.my.cnf
    echo "[bench] world-readable ~/.my.cnf with root password"
    ;;

  cred-aws-creds)
    mkdir -p /home/lowpriv/.aws
    cat >/home/lowpriv/.aws/credentials <<'EOF'
[default]
aws_access_key_id=AKIABENCH
aws_secret_access_key=SuperSecret
root_password=password
EOF
    chmod -R 755 /home/lowpriv/.aws
    chmod 644 /home/lowpriv/.aws/credentials
    chown -R lowpriv:lowpriv /home/lowpriv/.aws
    echo "[bench] world-readable ~/.aws/credentials with root password"
    ;;

  redis-unauth)
    userdel -f redis 2>/dev/null || true
    mkdir -p /root/.ssh /var/lib/redis /var/run/redis
    chmod 700 /root/.ssh
    redis-server --daemonize yes \
      --bind 127.0.0.1 \
      --port 6379 \
      --protected-mode no \
      --save "" \
      --dir /var/lib/redis \
      --enable-protected-configs yes 2>/dev/null || \
    redis-server --daemonize yes \
      --bind 127.0.0.1 \
      --port 6379 \
      --protected-mode no \
      --save "" \
      --dir /var/lib/redis
    echo "[bench] unauthenticated redis on 127.0.0.1:6379 (root-owned writes)"
    ;;

  cred-wgetrc)
    cat >/home/lowpriv/.wgetrc <<'EOF'
user=root
password=password
EOF
    chmod 644 /home/lowpriv/.wgetrc
    chown lowpriv:lowpriv /home/lowpriv/.wgetrc
    echo "[bench] world-readable ~/.wgetrc with root password"
    ;;

  cred-pgpass)
    cat >/home/lowpriv/.pgpass <<'EOF'
127.0.0.1:5432:bench:root:password
EOF
    chmod 644 /home/lowpriv/.pgpass
    chown lowpriv:lowpriv /home/lowpriv/.pgpass
    echo "[bench] world-readable ~/.pgpass with root password"
    ;;

  php-auto-prepend)
    mkdir -p /opt/bench
    printf '%s\n' '<?php // bench prepend stub' > /opt/bench/prepend.php
    printf '%s\n' '<?php // bench runner' > /opt/bench/run.php
    chmod 777 /opt/bench/prepend.php /opt/bench/run.php
    (
      while true; do
        php -d auto_prepend_file=/opt/bench/prepend.php /opt/bench/run.php 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "[bench] writable /opt/bench/prepend.php + root php poller"
    ;;

  writable:supervisor)
    mkdir -p /etc/supervisor/conf.d /opt/bench
    printf '%s\n' '; bench supervisor stub' > /etc/supervisor/conf.d/bench.conf
    chmod 666 /etc/supervisor/conf.d/bench.conf
    printf '%s\n' '#!/bin/sh' 'exit 0' > /opt/bench/supervisor-hook.sh
    chmod 777 /opt/bench/supervisor-hook.sh
    (
      while true; do
        /opt/bench/supervisor-hook.sh 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "[bench] writable supervisor conf.d + root hook poller"
    ;;

  writable:udev-rules)
    mkdir -p /etc/udev/rules.d /opt/bench
    printf '%s\n' '# bench udev stub' > /etc/udev/rules.d/99-bench.rules
    chmod 666 /etc/udev/rules.d/99-bench.rules
    printf '%s\n' '#!/bin/sh' 'exit 0' > /opt/bench/udev-hook.sh
    chmod 777 /opt/bench/udev-hook.sh
    (
      while true; do
        /opt/bench/udev-hook.sh 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "[bench] writable udev rules.d + root hook poller"
    ;;

  writable:systemd-dropin)
    mkdir -p /etc/systemd/system/bench.service.d /opt/bench
    printf '%s\n' '[Service]' > /etc/systemd/system/bench.service.d/override.conf
    chmod 666 /etc/systemd/system/bench.service.d/override.conf
    printf '%s\n' '#!/bin/sh' 'exit 0' > /opt/bench/systemd-hook.sh
    chmod 777 /opt/bench/systemd-hook.sh
    (
      while true; do
        /opt/bench/systemd-hook.sh 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "[bench] writable systemd unit drop-in + root hook poller"
    ;;

  cap-net-bind:*)
    name="${MISCONFIG#cap-net-bind:}"
    bin="$(resolve_bin "${name}")"
    bin="$(readlink -f "${bin}")"
    setcap 'cap_dac_read_search,cap_net_bind_service+ep' "${bin}"
    getcap "${bin}" || true
    echo "[bench] cap_dac_read_search,cap_net_bind_service+ep on ${bin}"
    ;;

  root-udp-service)
    mkdir -p /opt/bench
    cat >/opt/bench/rootudp.py <<'EOF'
#!/usr/bin/env python3
import socket, subprocess
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("127.0.0.1", 9998))
while True:
    data, addr = s.recvfrom(4096)
    if data.startswith(b"RUN "):
        cmd = data[4:].decode(errors="replace")
        try:
            out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, text=True)
        except subprocess.CalledProcessError as exc:
            out = exc.output or str(exc)
        s.sendto(out.encode(), addr)
EOF
    chmod 755 /opt/bench/rootudp.py
    nohup python3 /opt/bench/rootudp.py >/dev/null 2>&1 &
    echo "[bench] root UDP command service on 127.0.0.1:9998"
    ;;

  cred-env-local)
    cat >/home/lowpriv/.env <<'EOF'
APP_ENV=prod
ROOT_PASSWORD=password
EOF
    chmod 644 /home/lowpriv/.env
    chown lowpriv:lowpriv /home/lowpriv/.env
    echo "[bench] world-readable ~/.env with root password"
    ;;

  cred-docker-config)
    mkdir -p /home/lowpriv/.docker
    auth="$(printf '%s' 'root:password' | base64 -w0 2>/dev/null || printf '%s' 'root:password' | base64)"
    printf '%s\n' "{\"auths\":{\"registry.example.com\":{\"auth\":\"${auth}\"}}}" \
      >/home/lowpriv/.docker/config.json
    chmod 644 /home/lowpriv/.docker/config.json
    chown -R lowpriv:lowpriv /home/lowpriv/.docker
    echo "[bench] world-readable ~/.docker/config.json with root password"
    ;;

  cred-kubeconfig)
    mkdir -p /home/lowpriv/.kube
    cat >/home/lowpriv/.kube/config <<'EOF'
apiVersion: v1
kind: Config
users:
- name: bench
  user:
    token: password
EOF
    chmod 644 /home/lowpriv/.kube/config
    chown -R lowpriv:lowpriv /home/lowpriv/.kube
    echo "[bench] world-readable kubeconfig with root password token"
    ;;

  cred-jenkins-secrets)
    mkdir -p /home/lowpriv/jenkins_backup
    cat >/home/lowpriv/jenkins_backup/credentials.xml <<'EOF'
<com.cloudbees.plugins.credentials.SystemCredentialsProvider>
  <domainCredentialsMap>
    <entry>
      <string>_</string>
      <list>
        <com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl>
          <username>root</username>
          <password>password</password>
        </com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl>
      </list>
    </entry>
  </domainCredentialsMap>
</com.cloudbees.plugins.credentials.SystemCredentialsProvider>
EOF
    chmod 644 /home/lowpriv/jenkins_backup/credentials.xml
    chown -R lowpriv:lowpriv /home/lowpriv/jenkins_backup
    echo "[bench] world-readable Jenkins credentials backup"
    ;;

  cred-puppet-secrets)
    mkdir -p /etc/facter/facts.d
    printf '%s\n' '{"root_password":"password"}' > /etc/facter/facts.d/root_pass.json
    chmod 644 /etc/facter/facts.d/root_pass.json
    echo "[bench] world-readable facter facts with root password"
    ;;

  writable:etc-hosts)
    mkdir -p /opt/bench
    chmod 666 /etc/hosts
    printf '%s\n' '#!/bin/sh' 'exit 0' > /opt/bench/hosts-hook.sh
    chmod 777 /opt/bench/hosts-hook.sh
    (
      while true; do
        /opt/bench/hosts-hook.sh 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "[bench] writable /etc/hosts + root hook poller"
    ;;

  writable:rsyslog)
    mkdir -p /etc/rsyslog.d /opt/bench
    printf '%s\n' '# bench rsyslog stub' > /etc/rsyslog.d/bench.conf
    chmod 666 /etc/rsyslog.d/bench.conf
    printf '%s\n' '#!/bin/sh' 'exit 0' > /opt/bench/rsyslog-hook.sh
    chmod 777 /opt/bench/rsyslog-hook.sh
    (
      while true; do
        /opt/bench/rsyslog-hook.sh 2>/dev/null || true
        sleep 3
      done
    ) &
    echo "[bench] writable rsyslog.d + root hook poller"
    ;;

  writable:logrotate-d)
    mkdir -p /var/log/bench2 /etc/logrotate.d /opt/bench
    chmod 777 /opt/bench
    printf '%s\n' 'rotate2 log' > /var/log/bench2/app.log
    cat >/etc/logrotate.d/bench2 <<'EOF'
/var/log/bench2/*.log {
    size 1
    rotate 1
    missingok
    copytruncate
    postrotate
        /opt/bench/logrotate2-hook.sh
    endscript
}
EOF
    chmod 666 /etc/logrotate.d/bench2
    printf '%s\n' '#!/bin/sh' 'exit 0' > /opt/bench/logrotate2-hook.sh
    chmod 777 /opt/bench/logrotate2-hook.sh
    (
      while true; do
        chmod 644 /etc/logrotate.d/bench2 2>/dev/null || true
        logrotate -f /etc/logrotate.d/bench2 2>/dev/null || true
        chmod 666 /etc/logrotate.d/bench2 2>/dev/null || true
        sleep 5
      done
    ) &
    echo "[bench] writable logrotate.d drop-in + root poller"
    ;;

  kernel-detect-only)
    echo "[bench] baseline kernel surface for detect-only scoring"
    ;;

  cred-resolv-creds)
    cat >/home/lowpriv/resolv.override <<'EOF'
# resolver override
root_password=password
EOF
    chmod 644 /home/lowpriv/resolv.override
    chown lowpriv:lowpriv /home/lowpriv/resolv.override
    echo "[bench] world-readable resolver override with root password"
    ;;

  cred-tmux-conf)
    cat >/home/lowpriv/.tmux.conf <<'EOF'
# bench tmux leak
set-environment -g ROOT_PASS password
EOF
    chmod 644 /home/lowpriv/.tmux.conf
    chown lowpriv:lowpriv /home/lowpriv/.tmux.conf
    echo "[bench] world-readable ~/.tmux.conf with root password"
    ;;

  exploits-detect-only)
    mkdir -p /opt/bench
    uname -r > /opt/bench/kernel-version.txt
    chmod 644 /opt/bench/kernel-version.txt
    echo "[bench] readable kernel version hint file (detect-only)"
    ;;

  cred-npmrc)
    cat >/home/lowpriv/.npmrc <<'EOF'
root_password=password
//registry.npmjs.org/:_authToken=bench-leak-token
EOF
    chmod 644 /home/lowpriv/.npmrc
    chown lowpriv:lowpriv /home/lowpriv/.npmrc
    echo "[bench] world-readable ~/.npmrc with root password"
    ;;

  cred-ssh-config)
    mkdir -p /home/lowpriv/.ssh
    cat >/home/lowpriv/.ssh/config <<'EOF'
Host bench-root
  HostName 127.0.0.1
  User root
  # planted root password for lab: password
EOF
    chmod 644 /home/lowpriv/.ssh/config
    chown -R lowpriv:lowpriv /home/lowpriv/.ssh
    echo "[bench] world-readable ~/.ssh/config with root password hint"
    ;;

  cred-viminfo)
    cat >/home/lowpriv/.viminfo <<'EOF'
# Viminfo leak
> /root/flag.txt
    su root password
EOF
    chmod 644 /home/lowpriv/.viminfo
    chown lowpriv:lowpriv /home/lowpriv/.viminfo
    echo "[bench] world-readable ~/.viminfo with root password"
    ;;

  sudo-u-hash)
    write_sudoers_dropin "uhash" "lowpriv ALL=(ALL, !root) NOPASSWD: ALL"
    echo "[bench] sudo (ALL, !root) NOPASSWD ALL for CVE-2019-14287 style -u#-1"
    ;;

  apparmor-detect-only)
    mkdir -p /opt/bench
    if [[ -r /sys/module/apparmor/parameters/enabled ]]; then
      cat /sys/module/apparmor/parameters/enabled > /opt/bench/apparmor-enabled.txt
    else
      echo "unavailable" > /opt/bench/apparmor-enabled.txt
    fi
    chmod 644 /opt/bench/apparmor-enabled.txt
    echo "[bench] readable AppArmor enabled flag (detect-only)"
    ;;

  cred-lesshst)
    printf '%s\n' 'su root password' > /home/lowpriv/.lesshst
    chmod 644 /home/lowpriv/.lesshst
    chown lowpriv:lowpriv /home/lowpriv/.lesshst
    echo "[bench] world-readable ~/.lesshst with root password"
    ;;

  cred-gcloud)
    mkdir -p /home/lowpriv/.config/gcloud
    cat >/home/lowpriv/.config/gcloud/bench.properties <<'EOF'
root_password=password
EOF
    chmod 644 /home/lowpriv/.config/gcloud/bench.properties
    chown -R lowpriv:lowpriv /home/lowpriv/.config
    echo "[bench] world-readable gcloud config with root password"
    ;;

  cred-irssi)
    mkdir -p /home/lowpriv/.irssi
    cat >/home/lowpriv/.irssi/config <<'EOF'
servers = ( { password = "password"; } );
EOF
    chmod 644 /home/lowpriv/.irssi/config
    chown -R lowpriv:lowpriv /home/lowpriv/.irssi
    echo "[bench] world-readable irssi config with root password"
    ;;

  cred-muttrc)
    cat >/home/lowpriv/.muttrc <<'EOF'
set imap_pass=password
EOF
    chmod 644 /home/lowpriv/.muttrc
    chown lowpriv:lowpriv /home/lowpriv/.muttrc
    echo "[bench] world-readable ~/.muttrc with root password"
    ;;

  cred-s3cfg)
    cat >/home/lowpriv/.s3cfg <<'EOF'
[default]
access_key=AKIAEXAMPLE
secret_key=password
EOF
    chmod 644 /home/lowpriv/.s3cfg
    chown lowpriv:lowpriv /home/lowpriv/.s3cfg
    echo "[bench] world-readable ~/.s3cfg with root password reuse"
    ;;

  cred-bash-profile)
    cat >/home/lowpriv/.bash_profile <<'EOF'
export ROOT_PASS=password
EOF
    chmod 644 /home/lowpriv/.bash_profile
    chown lowpriv:lowpriv /home/lowpriv/.bash_profile
    echo "[bench] world-readable ~/.bash_profile with root password"
    ;;

  cred-screenlog)
    cat >/home/lowpriv/screenlog.0 <<'EOF'
root login password=password
EOF
    chmod 644 /home/lowpriv/screenlog.0
    chown lowpriv:lowpriv /home/lowpriv/screenlog.0
    echo "[bench] world-readable screenlog with root password"
    ;;

  cred-hg)
    mkdir -p /home/lowpriv/.config/hg
    cat >/home/lowpriv/.config/hg/hgrc <<'EOF'
[auth]
bench.prefix=*
bench.username=root
bench.password=password
EOF
    chmod 644 /home/lowpriv/.config/hg/hgrc
    chown -R lowpriv:lowpriv /home/lowpriv/.config
    echo "[bench] world-readable hgrc with root password"
    ;;

  cred-gitconfig-global)
    cat >/home/lowpriv/.gitconfig <<'EOF'
[credential]
helper = store
[bench]
rootPassword = password
EOF
    chmod 644 /home/lowpriv/.gitconfig
    chown lowpriv:lowpriv /home/lowpriv/.gitconfig
    echo "[bench] world-readable ~/.gitconfig with root password"
    ;;

  cred-msmtp)
    cat >/home/lowpriv/.msmtprc <<'EOF'
password password
EOF
    chmod 644 /home/lowpriv/.msmtprc
    chown lowpriv:lowpriv /home/lowpriv/.msmtprc
    echo "[bench] world-readable ~/.msmtprc with root password"
    ;;

  cred-ftp-netrc)
    cat >/home/lowpriv/.netrc <<'EOF'
machine ftp.example.com login root password password
EOF
    chmod 644 /home/lowpriv/.netrc
    chown lowpriv:lowpriv /home/lowpriv/.netrc
    echo "[bench] world-readable ~/.netrc FTP stanza with root password"
    ;;

  writable:shm-hook)
    mkdir -p /dev/shm/bench
    chmod 777 /dev/shm/bench
    printf '%s\n' '#!/bin/sh' 'exit 0' > /dev/shm/bench/hook.sh
    chmod 777 /dev/shm/bench/hook.sh
    printf '%s\n' '* * * * * root /bin/sh /dev/shm/bench/hook.sh' > /etc/cron.d/bench-shm
    chmod 644 /etc/cron.d/bench-shm
    (
      while true; do
        /bin/sh /dev/shm/bench/hook.sh >/dev/null 2>&1 || true
        sleep 3
      done
    ) &
    echo "[bench] writable /dev/shm/bench/hook.sh (+ root sh poller; shm is noexec)"
    ;;

  ptrace-detect-only)
    mkdir -p /opt/bench
    if [[ -r /proc/sys/kernel/yama/ptrace_scope ]]; then
      cat /proc/sys/kernel/yama/ptrace_scope > /opt/bench/ptrace-scope.txt
    else
      echo "unavailable" > /opt/bench/ptrace-scope.txt
    fi
    chmod 644 /opt/bench/ptrace-scope.txt
    echo "[bench] readable ptrace_scope (detect-only)"
    ;;

  selinux-detect-only)
    mkdir -p /opt/bench
    (command -v getenforce >/dev/null && getenforce || echo "unavailable") > /opt/bench/selinux-status.txt
    chmod 644 /opt/bench/selinux-status.txt
    echo "[bench] readable SELinux status (detect-only)"
    ;;

  docker-detect-only)
    mkdir -p /opt/bench
    {
      command -v docker >/dev/null && echo "docker-cli-present" || echo "docker-cli-absent"
      if [[ -S /var/run/docker.sock ]]; then echo "docker-sock-present"; else echo "docker-sock-absent"; fi
      id -nG lowpriv
    } > /opt/bench/docker-surface.txt
    chmod 644 /opt/bench/docker-surface.txt
    echo "[bench] readable docker surface hints (detect-only)"
    ;;

  fstab-detect-only)
    mkdir -p /opt/bench
    cp /etc/fstab /opt/bench/fstab.txt
    chmod 644 /opt/bench/fstab.txt
    echo "[bench] readable /etc/fstab copy (detect-only)"
    ;;

  capabilities-detect-only)
    mkdir -p /opt/bench
    {
      getcap -r /usr/bin 2>/dev/null | head -30 || true
      echo "/usr/bin/python3 cap_setuid=ep"
    } > /opt/bench/cap-hints.txt
    chmod 644 /opt/bench/cap-hints.txt
    echo "[bench] readable file capability hints (detect-only)"
    ;;

  writable:tmp-hook)
    mkdir -p /tmp/bench
    chmod 1777 /tmp
    chmod 777 /tmp/bench
    printf '%s\n' '#!/bin/sh' 'exit 0' > /tmp/bench/hook.sh
    chmod 777 /tmp/bench/hook.sh
    printf '%s\n' '* * * * * root /bin/sh /tmp/bench/hook.sh' > /etc/cron.d/bench-tmp
    chmod 644 /etc/cron.d/bench-tmp
    (
      while true; do
        /bin/sh /tmp/bench/hook.sh >/dev/null 2>&1 || true
        sleep 3
      done
    ) &
    echo "[bench] writable /tmp/bench/hook.sh (+ root sh poller)"
    ;;

  cred-subversion)
    mkdir -p /home/lowpriv/.subversion/auth/svn.simple
    printf '%s\n' 'root' 'password' > /home/lowpriv/.subversion/auth/svn.simple/bench
    chmod -R a+rX /home/lowpriv/.subversion
    chown -R lowpriv:lowpriv /home/lowpriv/.subversion
    echo "[bench] world-readable subversion auth leak"
    ;;

  cred-ldap)
    cat >/home/lowpriv/ldap.conf <<'EOF'
root_password password
EOF
    chmod 644 /home/lowpriv/ldap.conf
    chown lowpriv:lowpriv /home/lowpriv/ldap.conf
    echo "[bench] world-readable ldap.conf password leak"
    ;;

  cred-krb5)
    cat >/home/lowpriv/krb5.conf <<'EOF'
[libdefaults]
    default_realm = BENCH.LOCAL
    root_password = password
EOF
    chmod 644 /home/lowpriv/krb5.conf
    chown lowpriv:lowpriv /home/lowpriv/krb5.conf
    echo "[bench] world-readable krb5.conf password leak"
    ;;

  cred-chromium)
    mkdir -p /home/lowpriv/.config/chromium
    cat >/home/lowpriv/.config/chromium/bench_prefs.json <<'EOF'
{"credentials":{"root_password":"password"}}
EOF
    chmod 644 /home/lowpriv/.config/chromium/bench_prefs.json
    chown -R lowpriv:lowpriv /home/lowpriv/.config
    echo "[bench] world-readable chromium prefs leak"
    ;;

  cred-firefox)
    mkdir -p /home/lowpriv/.mozilla/firefox/bench.default
    cat >/home/lowpriv/.mozilla/firefox/bench.default/logins.json <<'EOF'
{"logins":[{"hostname":"bench","encryptedPassword":"password"}]}
EOF
    chmod 644 /home/lowpriv/.mozilla/firefox/bench.default/logins.json
    chown -R lowpriv:lowpriv /home/lowpriv/.mozilla
    echo "[bench] world-readable firefox logins leak"
    ;;

  cred-redis-cli)
    cat >/home/lowpriv/.rediscli.rc <<'EOF'
root_password password
EOF
    chmod 644 /home/lowpriv/.rediscli.rc
    chown lowpriv:lowpriv /home/lowpriv/.rediscli.rc
    echo "[bench] world-readable redis-cli rc leak"
    ;;

  cred-systemd-env)
    grep -q '^ROOT_PASS=' /etc/environment 2>/dev/null || echo 'ROOT_PASS=password' >> /etc/environment
    chmod 644 /etc/environment
    echo "[bench] world-readable /etc/environment root password"
    ;;

  cred-terraform)
    cat >/home/lowpriv/terraform.tfvars <<'EOF'
root_password = "password"
EOF
    chmod 644 /home/lowpriv/terraform.tfvars
    chown lowpriv:lowpriv /home/lowpriv/terraform.tfvars
    echo "[bench] world-readable terraform.tfvars leak"
    ;;

  cred-vault-token)
    cat >/home/lowpriv/.vault-token <<'EOF'
password
EOF
    chmod 644 /home/lowpriv/.vault-token
    chown lowpriv:lowpriv /home/lowpriv/.vault-token
    echo "[bench] world-readable vault token password reuse"
    ;;

  cred-filezilla)
    mkdir -p /home/lowpriv/.config/filezilla
    cat >/home/lowpriv/.config/filezilla/sitemanager.xml <<'EOF'
<User><Site><Pass encoding="plain">password</Pass></Site></User>
EOF
    chmod 644 /home/lowpriv/.config/filezilla/sitemanager.xml
    chown -R lowpriv:lowpriv /home/lowpriv/.config
    echo "[bench] world-readable filezilla sitemanager leak"
    ;;

  cred-msf4)
    mkdir -p /home/lowpriv/.msf4
    cat >/home/lowpriv/.msf4/config <<'EOF'
root_password=password
EOF
    chmod 644 /home/lowpriv/.msf4/config
    chown -R lowpriv:lowpriv /home/lowpriv/.msf4
    echo "[bench] world-readable msf4 config leak"
    ;;

  cred-secrets-yml)
    cat >/home/lowpriv/secrets.yml <<'EOF'
root_password: password
EOF
    chmod 644 /home/lowpriv/secrets.yml
    chown lowpriv:lowpriv /home/lowpriv/secrets.yml
    echo "[bench] world-readable secrets.yml leak"
    ;;

  cred-docker-env)
    mkdir -p /home/lowpriv/.docker
    cat >/home/lowpriv/.docker/.env <<'EOF'
ROOT_PASSWORD=password
EOF
    chmod 644 /home/lowpriv/.docker/.env
    chown -R lowpriv:lowpriv /home/lowpriv/.docker
    echo "[bench] world-readable ~/.docker/.env leak"
    ;;

  cred-ci-vars)
    cat >/home/lowpriv/ci.env <<'EOF'
ROOT_PASSWORD=password
EOF
    chmod 644 /home/lowpriv/ci.env
    chown lowpriv:lowpriv /home/lowpriv/ci.env
    echo "[bench] world-readable ci.env leak"
    ;;

  cred-keepass)
    cat >/home/lowpriv/keepass-export.xml <<'EOF'
<Password>password</Password>
EOF
    chmod 644 /home/lowpriv/keepass-export.xml
    chown lowpriv:lowpriv /home/lowpriv/keepass-export.xml
    echo "[bench] world-readable keepass export leak"
    ;;

  namespaces-detect-only)
    mkdir -p /opt/bench
    if [[ -r /proc/sys/kernel/unprivileged_userns_clone ]]; then
      cat /proc/sys/kernel/unprivileged_userns_clone > /opt/bench/userns-clone.txt
    else
      echo "unavailable" > /opt/bench/userns-clone.txt
    fi
    chmod 644 /opt/bench/userns-clone.txt
    echo "[bench] readable user namespace sysctl (detect-only)"
    ;;

  pkexec-detect-only)
    mkdir -p /opt/bench
    {
      command -v pkexec >/dev/null && pkexec --version 2>/dev/null || echo "pkexec-absent"
      ls -la /usr/bin/pkexec 2>/dev/null || true
    } > /opt/bench/pkexec-surface.txt
    chmod 644 /opt/bench/pkexec-surface.txt
    echo "[bench] readable pkexec surface (detect-only)"
    ;;

  sudo-version-detect-only)
    mkdir -p /opt/bench
    sudo -V 2>/dev/null | head -1 > /opt/bench/sudo-version.txt || echo "unavailable" > /opt/bench/sudo-version.txt
    chmod 644 /opt/bench/sudo-version.txt
    echo "[bench] readable sudo version (detect-only)"
    ;;

  writable:environment)
    touch /etc/environment
    chmod 666 /etc/environment
    (
      while true; do
        set -a
        # shellcheck disable=SC1091
        . /etc/environment 2>/dev/null || true
        set +a
        runme >/dev/null 2>&1 || true
        sleep 3
      done
    ) &
    echo "[bench] writable /etc/environment (+ root PATH poller via runme)"
    ;;

  cred-pypirc)
    cat >/home/lowpriv/.pypirc <<'EOF'
[distutils]
index-servers =
    pypi

[pypi]
password = password
EOF
    chmod 644 /home/lowpriv/.pypirc
    chown lowpriv:lowpriv /home/lowpriv/.pypirc
    echo "[bench] world-readable pypirc leak"
    ;;

  cred-rclone)
    mkdir -p /home/lowpriv/.config/rclone
    cat >/home/lowpriv/.config/rclone/rclone.conf <<'EOF'
[bench]
pass = password
EOF
    chmod 644 /home/lowpriv/.config/rclone/rclone.conf
    chown -R lowpriv:lowpriv /home/lowpriv/.config
    echo "[bench] world-readable rclone.conf leak"
    ;;

  cred-salt)
    mkdir -p /etc/salt
    cat >/etc/salt/minion <<'EOF'
root_password: password
EOF
    chmod 644 /etc/salt/minion
    echo "[bench] world-readable salt minion leak"
    ;;

  cred-chef)
    mkdir -p /etc/chef
    cat >/etc/chef/client.rb <<'EOF'
root_password "password"
EOF
    chmod 644 /etc/chef/client.rb
    echo "[bench] world-readable chef client.rb leak"
    ;;

  cred-pass-store)
    mkdir -p /home/lowpriv/.password-store
    cat >/home/lowpriv/.password-store/root.gpg <<'EOF'
root_password=password
EOF
    chmod 644 /home/lowpriv/.password-store/root.gpg
    chown -R lowpriv:lowpriv /home/lowpriv/.password-store
    echo "[bench] world-readable pass-store hint leak"
    ;;

  cred-gnupg)
    cat >/home/lowpriv/.gpg-passphrase <<'EOF'
password
EOF
    chmod 644 /home/lowpriv/.gpg-passphrase
    chown lowpriv:lowpriv /home/lowpriv/.gpg-passphrase
    echo "[bench] world-readable gpg passphrase leak"
    ;;

  cred-mongodb)
    cat >/home/lowpriv/.mongorc.js <<'EOF'
// root password: password
EOF
    chmod 644 /home/lowpriv/.mongorc.js
    chown lowpriv:lowpriv /home/lowpriv/.mongorc.js
    echo "[bench] world-readable mongorc.js leak"
    ;;

  cred-slack)
    cat >/home/lowpriv/.slack-token <<'EOF'
root_password=password
EOF
    chmod 644 /home/lowpriv/.slack-token
    chown lowpriv:lowpriv /home/lowpriv/.slack-token
    echo "[bench] world-readable slack token leak"
    ;;

  cred-boto)
    cat >/home/lowpriv/.boto <<'EOF'
[Credentials]
root_password = password
EOF
    chmod 644 /home/lowpriv/.boto
    chown lowpriv:lowpriv /home/lowpriv/.boto
    echo "[bench] world-readable boto credentials leak"
    ;;

  cred-pip-conf)
    mkdir -p /home/lowpriv/.config/pip
    cat >/home/lowpriv/.config/pip/pip.conf <<'EOF'
[global]
root_password = password
EOF
    chmod 644 /home/lowpriv/.config/pip/pip.conf
    chown -R lowpriv:lowpriv /home/lowpriv/.config
    echo "[bench] world-readable pip.conf leak"
    ;;

  cred-tokens-json)
    cat >/home/lowpriv/tokens.json <<'EOF'
{"root_password":"password"}
EOF
    chmod 644 /home/lowpriv/tokens.json
    chown lowpriv:lowpriv /home/lowpriv/tokens.json
    echo "[bench] world-readable tokens.json leak"
    ;;

  cred-openvpn)
    cat >/home/lowpriv/openvpn.auth <<'EOF'
root
password
EOF
    chmod 644 /home/lowpriv/openvpn.auth
    chown lowpriv:lowpriv /home/lowpriv/openvpn.auth
    echo "[bench] world-readable openvpn auth leak"
    ;;

  dbus-detect-only)
    mkdir -p /opt/bench
    {
      command -v dbus-daemon >/dev/null && echo "dbus-daemon-present" || echo "dbus-daemon-absent"
      ls -la /var/run/dbus/system_bus_socket 2>/dev/null || echo "no-system-bus-socket"
    } > /opt/bench/dbus-surface.txt
    chmod 644 /opt/bench/dbus-surface.txt
    echo "[bench] readable dbus surface (detect-only)"
    ;;

  cgroup-detect-only)
    mkdir -p /opt/bench
    {
      mount | grep -E 'cgroup|cpuset' || true
      test -d /sys/fs/cgroup && ls /sys/fs/cgroup | head -5 || true
    } > /opt/bench/cgroup-surface.txt
    chmod 644 /opt/bench/cgroup-surface.txt
    echo "[bench] readable cgroup surface (detect-only)"
    ;;

  mounts-detect-only)
    mkdir -p /opt/bench
    mount > /opt/bench/mounts-surface.txt
    chmod 644 /opt/bench/mounts-surface.txt
    echo "[bench] readable mount table (detect-only)"
    ;;

  *)
    echo "[bench] unknown MISCONFIG=${MISCONFIG}" >&2
    exit 1
    ;;
esac
