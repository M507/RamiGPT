# BeRoot coverage per benchmark target

One row per lab in the RamiGPT benchmark suite (**285** targets). Indicates whether
[BeRoot](../../tools/beroot/Linux/) would surface the intentional misconfiguration when
run as `lowpriv` (as in benchmark / `ramigpt/web/tools/beroot.py`).

**Remote verification** on `10.10.1.109` (cred: 62 Yes, 1 Partial; other: 81 Yes, 84 Partial, 57 No) — see [`beroot-cred-verify.json`](beroot-cred-verify.json) and [`beroot-verify.json`](beroot-verify.json).



## Legend

| Verdict | Meaning |
|---------|---------|
| **Yes** | BeRoot has a check that reliably flags the primary misconfiguration (sudo labs include the runner's `sudo -l` enrichment when BeRoot's `sudo -ll` parser misses rules). |
| **Partial** | BeRoot may show a related signal (e.g. NOPASSWD rule but not the env_keep/writable-hook chain; SUID binary but not custom `system()` abuse; exploit-suggester hints). |
| **No** | No BeRoot check covers this vector (credentials, network services, doas, SGID, most custom writable paths, etc.). |

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
| Yes | 143 |
| Partial | 85 |
| No | 57 |
| **Total** | **285** |

## All targets

| Target | Port | Family | BeRoot finds? | Notes |
|--------|-----:|--------|:-------------:|-------|
| `apparmor-detect-only` | 2362 | services | **No** | verified 2026-07-22 on 10.10.1.109 — no AppArmor check |
| `at-allow` | 2245 | writable | **Yes** | file_permissions (verified 2026-07-22 on 10.10.1.109) — path: /etc/at.allow [writable] |
| `cap-chown` | 2180 | capabilities | **Yes** | capabilities (verified 2026-07-22 on 10.10.1.109) — /usr/bin/python3.14 cap_chown: ep |
| `cap-dac-override` | 2184 | capabilities | **Yes** | capabilities (verified 2026-07-22 on 10.10.1.109) — /usr/bin/python3.14 cap_dac_override: ep |
| `cap-dac-read` | 2228 | capabilities | **Yes** | capabilities (verified 2026-07-22 on 10.10.1.109) — /usr/bin/python3.14 cap_dac_read_search: ep |
| `cap-fowner` | 2185 | capabilities | **Yes** | capabilities (verified 2026-07-22 on 10.10.1.109) — /usr/bin/python3.14 cap_fowner: ep |
| `cap-fsetid` | 2189 | capabilities | **Yes** | capabilities (verified 2026-07-22 on 10.10.1.109) — /usr/bin/python3.14 cap_fowner,cap_fsetid: ep |
| `cap-net-bind` | 2315 | capabilities | **Yes** | capabilities (verified 2026-07-22 on 10.10.1.109) — /usr/bin/python3.14 cap_dac_read_search,cap_net_bind_service: ep |
| `cap-python` | 2218 | capabilities | **Yes** | capabilities (verified 2026-07-22 on 10.10.1.109) — /usr/bin/python3.14 cap_setuid: ep |
| `cap-setfcap` | 2267 | capabilities | **Yes** | capabilities (verified 2026-07-22 on 10.10.1.109) — /usr/bin/python3.14 cap_fowner,cap_fsetid: ep |
| `capabilities-detect-only` | 2391 | services | **No** | verified 2026-07-22 on 10.10.1.109 — no capabilities output |
| `cgroup-detect-only` | 2450 | services | **No** | verified 2026-07-22 on 10.10.1.109 — no cgroup check |
| `cred-adm-log` | 2181 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /var/log/bench-secure.log: Jul 15 12:00:01 bench NOTE: root password for break-glass is: password |
| `cred-ansible` | 2239 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.ansible/vault_pass.txt: password \| /opt/ansible/group_vars_all.yml: ansible_ssh_pass: password |
| `cred-aws-creds` | 2298 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.aws/credentials: root_password=password |
| `cred-backup-secrets` | 2280 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /var/backups/credentials.txt: root_password=password |
| `cred-bash-profile` | 2383 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.bash_profile: export ROOT_PASS=password |
| `cred-boto` | 2446 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.boto: root_password = password |
| `cred-chef` | 2441 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /etc/chef/client.rb: root_password "password" |
| `cred-chromium` | 2410 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.config/chromium/bench_prefs.json: {"credentials":{"root_password":"password"}} |
| `cred-ci-vars` | 2423 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/ci.env: ROOT_PASSWORD=password |
| `cred-cleartext` | 2177 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/credentials.txt: root_password=password |
| `cred-core-dump` | 2241 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /var/crash/bench-app.core: recover password: password |
| `cred-docker-config` | 2318 | credentials | **Partial** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.docker/config.json: {"auths":{"registry.example.com":{"auth":"cm9vdDpwYXNzd29yZA=="}}} |
| `cred-docker-env` | 2422 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.docker/.env: ROOT_PASSWORD=password |
| `cred-env-file` | 2274 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /etc/environment: ROOT_PASS=password |
| `cred-env-local` | 2317 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.env: ROOT_PASSWORD=password |
| `cred-filezilla` | 2416 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.config/filezilla/sitemanager.xml: <User><Site><Pass encoding="plain">password</Pass></Site></User> |
| `cred-firefox` | 2411 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.mozilla/firefox/bench.default/logins.json: {"logins":[{"hostname":"bench","encryptedPassword":"password"}]} |
| `cred-ftp-netrc` | 2394 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.netrc: machine ftp.example.com login root password password |
| `cred-gcloud` | 2379 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.config/gcloud/bench.properties: root_password=password |
| `cred-git-config` | 2288 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.git-credentials: https://root:password@127.0.0.1 |
| `cred-gitconfig-global` | 2392 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.gitconfig: rootPassword = password |
| `cred-gnupg` | 2443 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.gpg-passphrase: password |
| `cred-hg` | 2385 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.config/hg/hgrc: bench.password=password |
| `cred-history` | 2178 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.bash_history: # root password is: password |
| `cred-irssi` | 2380 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.irssi/config: servers = ( { password = "password"; } ); |
| `cred-jenkins-secrets` | 2320 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/jenkins_backup/credentials.xml: <password>password</password> |
| `cred-keepass` | 2424 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/keepass-export.xml: <Password>password</Password> |
| `cred-krb5` | 2409 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/krb5.conf: root_password = password |
| `cred-kubeconfig` | 2319 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.kube/config: token: password |
| `cred-ldap` | 2408 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/ldap.conf: root_password password |
| `cred-lesshst` | 2378 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.lesshst: su root password |
| `cred-mongodb` | 2444 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.mongorc.js: // root password: password |
| `cred-msf4` | 2420 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.msf4/config: root_password=password |
| `cred-msmtp` | 2393 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.msmtprc: password password |
| `cred-muttrc` | 2381 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.muttrc: set imap_pass=password |
| `cred-mysql-cnf` | 2297 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.my.cnf: password=password |
| `cred-netrc` | 2287 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.netrc: login root |
| `cred-npmrc` | 2360 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.npmrc: root_password=password |
| `cred-openvpn` | 2454 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/openvpn.auth: root / password |
| `cred-pass-store` | 2442 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.password-store/root.gpg: root_password=password |
| `cred-pgpass` | 2302 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.pgpass: 127.0.0.1:5432:bench:root:password |
| `cred-pip-conf` | 2447 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.config/pip/pip.conf: root_password = password |
| `cred-puppet-secrets` | 2321 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /etc/facter/facts.d/root_pass.json: {"root_password":"password"} |
| `cred-pypirc` | 2438 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.pypirc: password = password |
| `cred-rclone` | 2439 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.config/rclone/rclone.conf: pass = password |
| `cred-redis-cli` | 2412 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.rediscli.rc: root_password password |
| `cred-resolv-creds` | 2342 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/resolv.override: root_password=password |
| `cred-root-key` | 2230 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/root_id_rsa [readable private key] \| /tmp/root_id_rsa [readable private key] |
| `cred-s3cfg` | 2382 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.s3cfg: secret_key=password |
| `cred-salt` | 2440 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /etc/salt/minion: root_password: password |
| `cred-screenlog` | 2384 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/screenlog.0: root login password=password |
| `cred-secrets-yml` | 2421 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/secrets.yml: root_password: password |
| `cred-shadow-read` | 2227 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /etc/shadow [readable] |
| `cred-slack` | 2445 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.slack-token: root_password=password |
| `cred-ssh-config` | 2361 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.ssh/config: # planted root password for lab: password |
| `cred-subversion` | 2407 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.subversion/auth/svn.simple/bench: root |
| `cred-systemd-env` | 2413 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /etc/environment: ROOT_PASS=password |
| `cred-terraform` | 2414 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/terraform.tfvars: root_password = "password" |
| `cred-tmux-conf` | 2346 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.tmux.conf: set-environment -g ROOT_PASS password |
| `cred-tokens-json` | 2448 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/tokens.json: {"root_password":"password"} |
| `cred-vault-token` | 2415 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.vault-token: password |
| `cred-viminfo` | 2364 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.viminfo: su root password |
| `cred-wgetrc` | 2301 | credentials | **Yes** | credential_leaks (verified 2026-07-22 on 10.10.1.109) — /home/lowpriv/.wgetrc: password=password |
| `dbus-detect-only` | 2449 | services | **No** | verified 2026-07-22 on 10.10.1.109 — no D-Bus policy check |
| `doas-nopass` | 2273 | doas | **No** | verified 2026-07-22 on 10.10.1.109 — no doas.conf check |
| `docker-detect-only` | 2389 | services | **No** | verified 2026-07-22 on 10.10.1.109 — docker not detected |
| `exploits-detect-only` | 2349 | services | **Partial** | verified 2026-07-22 on 10.10.1.109 — [1;37mAvailable information:[0m \| Kernel version: [1;32m5.4.0[0m \| Architecture: [1;32mx86_64[ |
| `fstab-detect-only` | 2390 | services | **No** | verified 2026-07-22 on 10.10.1.109 — no fstab/mount check |
| `kernel-detect-only` | 2339 | services | **Partial** | verified 2026-07-22 on 10.10.1.109 — [1;37mAvailable information:[0m \| Kernel version: [1;32m5.4.0[0m \| Architecture: [1;32mx86_64[ |
| `ld-preload-script` | 2246 | path | **No** | verified 2026-07-22 on 10.10.1.109 — no PATH poller / localhost service checks |
| `logrotate-writable` | 2240 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `mounts-detect-only` | 2451 | services | **No** | verified 2026-07-22 on 10.10.1.109 — no mount enumeration |
| `mysql-socket` | 2263 | credentials | **No** | verified 2026-07-22 on 10.10.1.109 — no credential/config leak scanner for this vector |
| `namespaces-detect-only` | 2417 | services | **No** | verified 2026-07-22 on 10.10.1.109 — no user-namespace abuse check |
| `nfs-exports` | 2220 | nfs | **No** | verified 2026-07-22 on 10.10.1.109 — no NFS exports signal |
| `node-path-hijack` | 2260 | path | **No** | verified 2026-07-22 on 10.10.1.109 — no PATH poller / localhost service checks |
| `path-hijack` | 2232 | path | **No** | verified 2026-07-22 on 10.10.1.109 — no PATH poller / localhost service checks |
| `php-auto-prepend` | 2310 | python | **No** | verified 2026-07-22 on 10.10.1.109 — not on sys.path; no PHP/Node include checks |
| `php-include-hijack` | 2259 | python | **No** | verified 2026-07-22 on 10.10.1.109 — not on sys.path; no PHP/Node include checks |
| `pkexec-detect-only` | 2418 | services | **No** | verified 2026-07-22 on 10.10.1.109 — no pkexec rule/version check |
| `ptrace-detect-only` | 2387 | services | **No** | verified 2026-07-22 on 10.10.1.109 — no ptrace output |
| `python-cwd` | 2238 | python | **No** | verified 2026-07-22 on 10.10.1.109 — not on sys.path; no PHP/Node include checks |
| `python-hijack` | 2219 | python | **Yes** | verified 2026-07-22 on 10.10.1.109 — /usr/lib/python3.14 |
| `rbash-escape` | 2251 | shell | **No** | verified 2026-07-22 on 10.10.1.109 — no restricted-shell check; BeRoot upload blocked in rbash |
| `redis-unauth` | 2300 | services | **No** | verified 2026-07-22 on 10.10.1.109 — no network service / socket enumeration |
| `root-tcp-service` | 2261 | path | **No** | verified 2026-07-22 on 10.10.1.109 — no PATH poller / localhost service checks |
| `root-udp-service` | 2316 | services | **No** | verified 2026-07-22 on 10.10.1.109 — no network service / socket enumeration |
| `selinux-detect-only` | 2388 | services | **No** | verified 2026-07-22 on 10.10.1.109 — no SELinux check |
| `sgid-secret` | 2231 | sgid | **No** | verified 2026-07-22 on 10.10.1.109 — suid_bins scans SUID only, not SGID |
| `sudo-all` | 2170 | sudo-advanced | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: all \| ALL: all permissions \| Matching Defaults entries for lowpriv |
| `sudo-ansible` | 2275 | sudo-advanced | **Partial** | verified 2026-07-22 on 10.10.1.109 — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local |
| `sudo-awk` | 2212 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/awk \| gtfobins found (gawk): \| - sudo gawk 'BEGIN {system |
| `sudo-backup` | 2265 | sudo-advanced | **Partial** | verified 2026-07-22 on 10.10.1.109 — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local |
| `sudo-base64` | 2281 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/base64 \| gtfobins found (base64): \| - LFILE=file_to_read |
| `sudo-bash` | 2179 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /bin/bash \| gtfobins found (bash): \| - sudo bash \| Matching Defaul |
| `sudo-bash-env` | 2193 | sudo-advanced | **Partial** | verified 2026-07-22 on 10.10.1.109 — ### Rules for lowpriv ### \| rule: /bin/bash \| gtfobins found (bash): \| - sudo bash \| Matching Defaul |
| `sudo-cat` | 2290 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/cat \| gtfobins found (cat): \| - LFILE=file_to_read \| - su |
| `sudo-chmod` | 2191 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /bin/chmod \| gtfobins found (chmod): \| - LFILE=file_to_change \| - |
| `sudo-column` | 2327 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/column \| gtfobins found (column): \| - LFILE=file_to_read |
| `sudo-comm` | 2329 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/comm \| gtfobins found (comm): \| - LFILE=file_to_read \| - |
| `sudo-composer` | 2247 | sudo-advanced | **Partial** | verified 2026-07-22 on 10.10.1.109 — ### Rules for lowpriv ### \| rule: /usr/bin/composer \| gtfobins found (composer): \| - TF=$(mktemp -d) |
| `sudo-cp` | 2222 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local |
| `sudo-csplit` | 2352 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/csplit \| gtfobins found (csplit): \| - LFILE=file_to_read |
| `sudo-curl` | 2203 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/curl \| gtfobins found (curl): \| - URL=http://attacker.com |
| `sudo-cut` | 2282 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/cut \| gtfobins found (cut): \| - LFILE=file_to_read \| - su |
| `sudo-dd` | 2192 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — verify skipped: SSH auth failed on 2026-07-22 (expected NOPASSWD /bin/dd) |
| `sudo-diff` | 2306 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/diff \| gtfobins found (diff): \| - LFILE=file_to_read \| - |
| `sudo-dos2unix` | 2400 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local |
| `sudo-ed` | 2435 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/ed \| gtfobins found (ed): \| - sudo ed \| - !/bin/sh \| Matc |
| `sudo-egrep` | 2398 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local |
| `sudo-env` | 2210 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/env \| gtfobins found (env): \| - sudo env /bin/sh \| Matchi |
| `sudo-expand` | 2314 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/expand \| gtfobins found (expand): \| - LFILE=file_to_read |
| `sudo-find` | 2205 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/find \| gtfobins found (find): \| - sudo find . -exec /bin/ |
| `sudo-fmt` | 2328 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/fmt \| gtfobins found (fmt): \| - LFILE=file_to_read \| - su |
| `sudo-fold` | 2322 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/fold \| gtfobins found (fold): \| - LFILE=file_to_read \| - |
| `sudo-gem` | 2250 | sudo-advanced | **Partial** | verified 2026-07-22 on 10.10.1.109 — ### Rules for lowpriv ### \| rule: /usr/bin/gem \| gtfobins found (gem): \| - sudo gem open -e "/bin/sh |
| `sudo-git-hook` | 2244 | sudo-advanced | **Partial** | verified 2026-07-22 on 10.10.1.109 — ### Rules for lowpriv ### \| rule: /usr/bin/git \| gtfobins found (git): \| - sudo PAGER='sh -c "exec s |
| `sudo-grep` | 2294 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/grep \| gtfobins found (grep): \| - LFILE=file_to_read \| - |
| `sudo-group` | 2171 | sudo-advanced | **Partial** | verified 2026-07-22 on 10.10.1.109 — ### Rules for lowpriv ### \| rule: /usr/bin/env \| gtfobins found (env): \| - sudo env /bin/sh \| Matchi |
| `sudo-hd` | 2323 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/hd \| gtfobins found (hexdump): \| - LFILE=file_to_read \| - |
| `sudo-head` | 2291 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/head \| gtfobins found (head): \| - LFILE=file_to_read \| - |
| `sudo-hexdump` | 2350 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/hexdump \| gtfobins found (hexdump): \| - LFILE=file_to_rea |
| `sudo-iconv` | 2354 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/iconv \| gtfobins found (iconv): \| - LFILE=file_to_read \| |
| `sudo-install` | 2198 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/install \| gtfobins found (install): \| - LFILE=file_to_cha |
| `sudo-join` | 2351 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/join \| gtfobins found (join): \| - LFILE=file_to_read \| - |
| `sudo-jq` | 2373 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/jq \| gtfobins found (jq): \| - LFILE=file_to_read \| - sudo |
| `sudo-ld-library-path` | 2183 | sudo-advanced | **Partial** | verified 2026-07-22 on 10.10.1.109 — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local |
| `sudo-ld-preload` | 2213 | sudo-advanced | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — Directive found \| ### Rules for lowpriv ### \| rule: /usr/bin/find \| gtfobins found (find): \| - sudo |
| `sudo-less` | 2206 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/less \| gtfobins found (less): \| - sudo less /etc/profile |
| `sudo-lua` | 2405 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local |
| `sudo-more` | 2353 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/more \| gtfobins found (more): \| - TERM= sudo more /etc/pr |
| `sudo-mv` | 2196 | sudo | **Partial** | sudo_list (writable hook/script path often outside scanned file list) (verified 2026-07-22 on 10.10.1.109) — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/sn |
| `sudo-nano` | 2207 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/nano \| gtfobins found (nano): \| - sudo nano \| - ^R^X \| - |
| `sudo-nl` | 2293 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/nl \| gtfobins found (nl): \| - LFILE=file_to_read \| - sudo |
| `sudo-noauth` | 2233 | sudo-advanced | **Partial** | verified 2026-07-22 on 10.10.1.109 — ### Rules for lowpriv ### \| rule: all \| ALL: all permissions \| Matching Defaults entries for lowpriv |
| `sudo-node` | 2371 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/node \| gtfobins found (node): \| - sudo node -e 'child_pro |
| `sudo-nodepath` | 2272 | sudo-advanced | **Partial** | verified 2026-07-22 on 10.10.1.109 — ### Rules for lowpriv ### \| rule: /usr/bin/node \| gtfobins found (node): \| - sudo node -e 'child_pro |
| `sudo-npm` | 2252 | sudo-advanced | **Partial** | verified 2026-07-22 on 10.10.1.109 — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local |
| `sudo-od` | 2277 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/od \| gtfobins found (od): \| - LFILE=file_to_read \| - sudo |
| `sudo-openssl` | 2283 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/openssl \| gtfobins found (openssl): \| - RHOST=attacker.co |
| `sudo-paste` | 2324 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/paste \| gtfobins found (paste): \| - LFILE=file_to_read \| |
| `sudo-perl` | 2365 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/perl \| gtfobins found (perl): \| - sudo perl -e 'exec "/bi |
| `sudo-perl-exec` | 2279 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/perl \| gtfobins found (perl): \| - sudo perl -e 'exec "/bi |
| `sudo-perl5lib` | 2194 | sudo-advanced | **Partial** | verified 2026-07-22 on 10.10.1.109 — ### Rules for lowpriv ### \| rule: /usr/bin/perl \| gtfobins found (perl): \| - sudo perl -e 'exec "/bi |
| `sudo-php` | 2367 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local |
| `sudo-pip` | 2248 | sudo-advanced | **Partial** | verified 2026-07-22 on 10.10.1.109 — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local |
| `sudo-pr` | 2304 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/pr \| gtfobins found (pr): \| - LFILE=file_to_read \| - pr - |
| `sudo-ps4` | 2254 | sudo-advanced | **Partial** | verified 2026-07-22 on 10.10.1.109 — ### Rules for lowpriv ### \| rule: /bin/bash \| gtfobins found (bash): \| - sudo bash \| Matching Defaul |
| `sudo-ptx` | 2330 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local |
| `sudo-python` | 2208 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local |
| `sudo-pythonpath` | 2173 | sudo-advanced | **Partial** | verified 2026-07-22 on 10.10.1.109 — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local |
| `sudo-rev` | 2325 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/rev \| gtfobins found (rev): \| - LFILE=file_to_read \| - su |
| `sudo-rsync` | 2376 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/rsync \| gtfobins found (rsync): \| - sudo rsync -e 'sh -c |
| `sudo-ruby` | 2369 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local |
| `sudo-rubylib` | 2223 | sudo-advanced | **Partial** | verified 2026-07-22 on 10.10.1.109 — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local |
| `sudo-runas` | 2234 | sudo-advanced | **Partial** | verified 2026-07-22 on 10.10.1.109 — ### Rules for lowpriv ### \| rule: all \| ALL: all permissions \| Matching Defaults entries for lowpriv |
| `sudo-scp` | 2375 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: all \| ALL: all permissions \| rule: /usr/bin/scp \| gtfobins found ( |
| `sudo-sed` | 2197 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /bin/sed \| gtfobins found (sed): \| - sudo sed -n '1e exec sh 1>&0' |
| `sudo-shelopts` | 2255 | sudo-advanced | **Partial** | verified 2026-07-22 on 10.10.1.109 — ### Rules for lowpriv ### \| rule: /bin/bash \| gtfobins found (bash): \| - sudo bash \| Matching Defaul |
| `sudo-shuf` | 2299 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/shuf \| gtfobins found (shuf): \| - LFILE=file_to_write \| - |
| `sudo-sort` | 2303 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/sort \| gtfobins found (sort): \| - LFILE=file_to_read \| - |
| `sudo-split` | 2348 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/split \| gtfobins found (split): \| - split --filter=/bin/s |
| `sudo-sqlite3` | 2396 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/sqlite3 \| gtfobins found (sqlite3): \| - sudo sqlite3 /dev |
| `sudo-strings` | 2268 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local |
| `sudo-tac` | 2326 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/tac \| gtfobins found (tac): \| - LFILE=file_to_read \| - su |
| `sudo-tail` | 2292 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/tail \| gtfobins found (tail): \| - LFILE=file_to_read \| - |
| `sudo-tar` | 2209 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/tar \| gtfobins found (tar): \| - sudo tar -cf /dev/null /d |
| `sudo-tee` | 2221 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: all \| ALL: all permissions \| rule: /usr/bin/tee \| gtfobins found ( |
| `sudo-u-hash` | 2363 | sudo-advanced | **Partial** | verified 2026-07-22 on 10.10.1.109 — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local |
| `sudo-uniq` | 2305 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/uniq \| gtfobins found (uniq): \| - LFILE=file_to_read \| - |
| `sudo-version-detect-only` | 2419 | services | **No** | verified 2026-07-22 on 10.10.1.109 — no sudo -V/CVE check |
| `sudo-vim` | 2211 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local |
| `sudo-wget` | 2204 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/wget \| gtfobins found (wget): \| - URL=http://attacker.com |
| `sudo-wildcard-tar` | 2236 | sudo-advanced | **Partial** | verified 2026-07-22 on 10.10.1.109 — Matching Defaults entries for lowpriv on ubuntu: \| env_reset, mail_badpass, \| secure_path=/usr/local |
| `sudo-writable-script` | 2172 | sudo-advanced | **Partial** | verified 2026-07-22 on 10.10.1.109 — ### Rules for lowpriv ### \| rule: /opt/bench/root.sh \| path: /opt/bench/root.sh [writable] \| Matchin |
| `sudo-xxd` | 2276 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/xxd \| gtfobins found (xxd): \| - LFILE=file_to_read \| - su |
| `sudo-yarn` | 2269 | sudo-advanced | **No** | verified 2026-07-22 on 10.10.1.109 — no sudo rule found |
| `sudo-zip` | 2289 | sudo | **Yes** | sudo_list (verified 2026-07-22 on 10.10.1.109) — ### Rules for lowpriv ### \| rule: /usr/bin/zip \| gtfobins found (zip): \| - TF=$(mktemp -u) \| - sudo |
| `suid-base64` | 2285 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-cat` | 2426 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-chmod` | 2195 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/bash \| [+] gtfobins found: \| - sudo bash \| /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount |
| `suid-column` | 2343 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-comm` | 2345 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-cp` | 2199 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/gnucp \| /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mou |
| `suid-csplit` | 2357 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-curl` | 2370 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-cut` | 2399 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-dd` | 2200 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-diff` | 2425 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/diff \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo diff --line-format=%L /dev/null |
| `suid-dlopen` | 2242 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /opt/bench/suid_dlopen \| /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - |
| `suid-dos2unix` | 2401 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-ed` | 2436 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-env` | 2202 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-expand` | 2358 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-find` | 2214 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/find \| [+] gtfobins found: \| - sudo find . -exec /bin/sh \; -quit \| /usr/bin/umount \| /usr/ |
| `suid-fmt` | 2344 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-fold` | 2331 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-gawk` | 2201 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-grep` | 2307 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/grep \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo grep '' $LFILE \| /usr/bin/umount |
| `suid-grep2` | 2427 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/grep \| [+] gtfobins found: \| - LFILE=file_to_read \| - sudo grep '' $LFILE \| /usr/bin/umount |
| `suid-hd` | 2332 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-head` | 2295 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-hexdump` | 2355 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-iconv` | 2359 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/iconv \| [+] gtfobins found: \| - LFILE=file_to_read \| - ./iconv -f 8859_1 |
| `suid-install` | 2434 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-install2` | 2453 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-join` | 2356 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-jq` | 2374 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-less` | 2452 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-lua` | 2406 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-more` | 2286 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/more \| [+] gtfobins found: \| - TERM= sudo more /etc/profile \| - !/bin/sh \| /usr/bin/umount |
| `suid-nl` | 2309 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-node` | 2372 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-od` | 2402 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-openssl` | 2429 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-paste` | 2335 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-path-hijack` | 2224 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /opt/bench/suid_path \| /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - su |
| `suid-perl` | 2366 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-php` | 2368 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-pr` | 2340 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-ptx` | 2347 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-python` | 2215 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-rev` | 2333 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-rsync` | 2377 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-sed` | 2432 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/sed \| [+] gtfobins found: \| - sudo sed -n '1e exec sh 1>&0' /etc/hosts \| /usr/bin/umount \| |
| `suid-shuf` | 2430 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-sort` | 2308 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-split` | 2403 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-sqlite3` | 2397 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-strings` | 2404 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-strings2` | 2433 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-tac` | 2334 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-tail` | 2296 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-uniq` | 2341 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-writable` | 2176 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-writable-exec` | 2225 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /opt/bench/suid_exec \| [+] exec calls found: \| - /opt/bench/helper [writable] \| /usr/bin/umount \| /u |
| `suid-xxd` | 2428 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `suid-zip` | 2431 | suid | **Partial** | verified 2026-07-22 on 10.10.1.109 — /usr/bin/umount \| /usr/bin/chsh \| /usr/bin/mount \| [+] gtfobins found: \| - sudo mount -o bind /bin/s |
| `wildcard-cron` | 2226 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-anacrontab` | 2270 | writable | **Yes** | file_permissions (verified 2026-07-22 on 10.10.1.109) — path: /etc/anacrontab [writable] |
| `writable-apache-config` | 2278 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-bashrc` | 2190 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-cron-allow` | 2249 | writable | **Yes** | file_permissions (verified 2026-07-22 on 10.10.1.109) — path: /etc/cron.allow [writable] |
| `writable-cron-d` | 2256 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-cron-ref` | 2186 | writable | **Yes** | file_permissions (verified 2026-07-22 on 10.10.1.109) — path: /etc/crontab \| subfiles: \| - [writable: /opt/bench/cronroot.sh] => * * * * * root /opt/bench/c |
| `writable-crontab` | 2216 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-crontab-system` | 2271 | writable | **Yes** | file_permissions (verified 2026-07-22 on 10.10.1.109) — path: /etc/crontab [writable] \| subfiles: \| - [writable: /opt/bench/system-cron-job] => * * * * * ro |
| `writable-environment` | 2437 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-etc-hosts` | 2336 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-exports` | 2187 | nfs | **No** | verified 2026-07-22 on 10.10.1.109 — no NFS exports signal |
| `writable-init-d` | 2253 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-ld-so-conf` | 2235 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-ld-so-preload` | 2182 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-lib` | 2237 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-logrotate-d` | 2338 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-motd` | 2243 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-nginx-config` | 2284 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-pam` | 2258 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-passwd` | 2217 | writable | **Yes** | file_permissions (verified 2026-07-22 on 10.10.1.109) — path: /etc/passwd [writable] |
| `writable-profile` | 2188 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-rc-local` | 2264 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-root-ssh` | 2229 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-rsyslog` | 2337 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-shadow` | 2174 | writable | **Yes** | file_permissions (verified 2026-07-22 on 10.10.1.109) — path: /etc/shadow [writable] |
| `writable-shm-hook` | 2386 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-sshd-config` | 2257 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-sudoers` | 2175 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-supervisor` | 2311 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-systemd-dropin` | 2313 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-tmp-hook` | 2395 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-udev-rules` | 2312 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-vpn-hook` | 2266 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
| `writable-webroot` | 2262 | writable | **No** | verified 2026-07-22 on 10.10.1.109 — path not in scanned file_permissions list |
