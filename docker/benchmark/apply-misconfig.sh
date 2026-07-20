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

  screen-root-socket)
    mkdir -p /etc/screen
    cat >/etc/screen/screenrc <<'EOF'
multiuser on
acladd lowpriv
EOF
    chmod 644 /etc/screen/screenrc
    screen -dmS bench sleep 999999
    chmod -R a+rwX /var/run/screen 2>/dev/null || true
    echo "[bench] root screen session bench (multiuser + acladd lowpriv)"
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

  *)
    echo "[bench] unknown MISCONFIG=${MISCONFIG}" >&2
    exit 1
    ;;
esac
