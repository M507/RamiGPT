# BeRoot coverage per benchmark target

One row per lab in the RamiGPT benchmark suite (**285** targets). Indicates whether
[BeRoot](../../tools/beroot/Linux/) would surface the intentional misconfiguration when
run as `lowpriv` (as in benchmark / `ramigpt/web/tools/beroot.py`).

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

## Summary

| Verdict | Count |
|---------|------:|
| Yes | 140 |
| Partial | 38 |
| No | 107 |
| **Total** | **285** |

## All targets

| Target | Port | Family | BeRoot finds? | Notes |
|--------|-----:|--------|:-------------:|-------|
| `apparmor-detect-only` | 2362 | services | **No** | no AppArmor check |
| `at-allow` | 2245 | writable | **Partial** | file_permissions — writable at job; /etc/at.allow scanned but job file may not be |
| `cap-chown` | 2180 | capabilities | **Yes** | capabilities (getcap -r) |
| `cap-dac-override` | 2184 | capabilities | **Yes** | capabilities (getcap -r) |
| `cap-dac-read` | 2228 | capabilities | **Yes** | capabilities (getcap -r) |
| `cap-fowner` | 2185 | capabilities | **Yes** | capabilities (getcap -r) |
| `cap-fsetid` | 2189 | capabilities | **Yes** | capabilities (getcap -r) |
| `cap-net-bind` | 2315 | capabilities | **Yes** | capabilities (getcap -r) |
| `cap-python` | 2218 | capabilities | **Yes** | capabilities (getcap -r) |
| `cap-setfcap` | 2267 | capabilities | **Yes** | capabilities (getcap -r) |
| `capabilities-detect-only` | 2391 | services | **Yes** | capabilities (getcap -r) |
| `cgroup-detect-only` | 2450 | services | **No** | no cgroup check |
| `cred-adm-log` | 2181 | credentials | **No** | no credential/config leak scanner |
| `cred-ansible` | 2239 | credentials | **No** | no credential/config leak scanner |
| `cred-aws-creds` | 2298 | credentials | **No** | no credential/config leak scanner |
| `cred-backup-secrets` | 2280 | credentials | **No** | no credential/config leak scanner |
| `cred-bash-profile` | 2383 | credentials | **No** | no credential/config leak scanner |
| `cred-boto` | 2446 | credentials | **No** | no credential/config leak scanner |
| `cred-chef` | 2441 | credentials | **No** | no credential/config leak scanner |
| `cred-chromium` | 2410 | credentials | **No** | no credential/config leak scanner |
| `cred-ci-vars` | 2423 | credentials | **No** | no credential/config leak scanner |
| `cred-cleartext` | 2177 | credentials | **No** | no credential/config leak scanner |
| `cred-core-dump` | 2241 | credentials | **No** | no credential/config leak scanner |
| `cred-docker-config` | 2318 | credentials | **No** | no credential/config leak scanner |
| `cred-docker-env` | 2422 | credentials | **No** | no credential/config leak scanner |
| `cred-env-file` | 2274 | credentials | **No** | no credential/config leak scanner |
| `cred-env-local` | 2317 | credentials | **No** | no credential/config leak scanner |
| `cred-filezilla` | 2416 | credentials | **No** | no credential/config leak scanner |
| `cred-firefox` | 2411 | credentials | **No** | no credential/config leak scanner |
| `cred-ftp-netrc` | 2394 | credentials | **No** | no credential/config leak scanner |
| `cred-gcloud` | 2379 | credentials | **No** | no credential/config leak scanner |
| `cred-git-config` | 2288 | credentials | **No** | no credential/config leak scanner |
| `cred-gitconfig-global` | 2392 | credentials | **No** | no credential/config leak scanner |
| `cred-gnupg` | 2443 | credentials | **No** | no credential/config leak scanner |
| `cred-hg` | 2385 | credentials | **No** | no credential/config leak scanner |
| `cred-history` | 2178 | credentials | **No** | no credential/config leak scanner |
| `cred-irssi` | 2380 | credentials | **No** | no credential/config leak scanner |
| `cred-jenkins-secrets` | 2320 | credentials | **No** | no credential/config leak scanner |
| `cred-keepass` | 2424 | credentials | **No** | no credential/config leak scanner |
| `cred-krb5` | 2409 | credentials | **No** | no credential/config leak scanner |
| `cred-kubeconfig` | 2319 | credentials | **No** | no credential/config leak scanner |
| `cred-ldap` | 2408 | credentials | **No** | no credential/config leak scanner |
| `cred-lesshst` | 2378 | credentials | **No** | no credential/config leak scanner |
| `cred-mongodb` | 2444 | credentials | **No** | no credential/config leak scanner |
| `cred-msf4` | 2420 | credentials | **No** | no credential/config leak scanner |
| `cred-msmtp` | 2393 | credentials | **No** | no credential/config leak scanner |
| `cred-muttrc` | 2381 | credentials | **No** | no credential/config leak scanner |
| `cred-mysql-cnf` | 2297 | credentials | **No** | no credential/config leak scanner |
| `cred-netrc` | 2287 | credentials | **No** | no credential/config leak scanner |
| `cred-npmrc` | 2360 | credentials | **No** | no credential/config leak scanner |
| `cred-openvpn` | 2454 | credentials | **No** | no credential/config leak scanner |
| `cred-pass-store` | 2442 | credentials | **No** | no credential/config leak scanner |
| `cred-pgpass` | 2302 | credentials | **No** | no credential/config leak scanner |
| `cred-pip-conf` | 2447 | credentials | **No** | no credential/config leak scanner |
| `cred-puppet-secrets` | 2321 | credentials | **No** | no credential/config leak scanner |
| `cred-pypirc` | 2438 | credentials | **No** | no credential/config leak scanner |
| `cred-rclone` | 2439 | credentials | **No** | no credential/config leak scanner |
| `cred-redis-cli` | 2412 | credentials | **No** | no credential/config leak scanner |
| `cred-resolv-creds` | 2342 | credentials | **No** | no credential/config leak scanner |
| `cred-root-key` | 2230 | credentials | **No** | no credential/config leak scanner |
| `cred-s3cfg` | 2382 | credentials | **No** | no credential/config leak scanner |
| `cred-salt` | 2440 | credentials | **No** | no credential/config leak scanner |
| `cred-screenlog` | 2384 | credentials | **No** | no credential/config leak scanner |
| `cred-secrets-yml` | 2421 | credentials | **No** | no credential/config leak scanner |
| `cred-shadow-read` | 2227 | credentials | **No** | no credential/config leak scanner |
| `cred-slack` | 2445 | credentials | **No** | no credential/config leak scanner |
| `cred-ssh-config` | 2361 | credentials | **No** | no credential/config leak scanner |
| `cred-subversion` | 2407 | credentials | **No** | no credential/config leak scanner |
| `cred-systemd-env` | 2413 | credentials | **No** | no credential/config leak scanner |
| `cred-terraform` | 2414 | credentials | **No** | no credential/config leak scanner |
| `cred-tmux-conf` | 2346 | credentials | **No** | no credential/config leak scanner |
| `cred-tokens-json` | 2448 | credentials | **No** | no credential/config leak scanner |
| `cred-vault-token` | 2415 | credentials | **No** | no credential/config leak scanner |
| `cred-viminfo` | 2364 | credentials | **No** | no credential/config leak scanner |
| `cred-wgetrc` | 2301 | credentials | **No** | no credential/config leak scanner |
| `dbus-detect-only` | 2449 | services | **No** | no D-Bus policy check |
| `doas-nopass` | 2273 | doas | **No** | no doas.conf check |
| `docker-detect-only` | 2389 | services | **Partial** | docker_installed / docker_mounted_sockets |
| `exploits-detect-only` | 2349 | services | **Partial** | exploits (linux-exploit-suggester) |
| `fstab-detect-only` | 2390 | services | **No** | no fstab/mount check |
| `kernel-detect-only` | 2339 | services | **Partial** | exploits (linux-exploit-suggester) |
| `ld-preload-script` | 2246 | path | **Partial** | file_permissions if script path is referenced from scanned config |
| `logrotate-writable` | 2240 | writable | **Partial** | file_permissions — postrotate script path not in default list |
| `mounts-detect-only` | 2451 | services | **No** | no mount enumeration |
| `mysql-socket` | 2263 | credentials | **No** | no credential/config leak scanner |
| `namespaces-detect-only` | 2417 | services | **No** | no user-namespace abuse check |
| `nfs-exports` | 2220 | nfs | **Yes** | nfs_root_squashing |
| `node-path-hijack` | 2260 | path | **No** | not on sys.path; no PHP/Node include checks |
| `path-hijack` | 2232 | path | **No** | no PATH poller / localhost service checks |
| `php-auto-prepend` | 2310 | python | **No** | not on sys.path; no PHP/Node include checks |
| `php-include-hijack` | 2259 | python | **No** | not on sys.path; no PHP/Node include checks |
| `pkexec-detect-only` | 2418 | services | **No** | no pkexec rule/version check |
| `ptrace-detect-only` | 2387 | services | **Partial** | ptrace_scope |
| `python-cwd` | 2238 | python | **No** | not on sys.path; no PHP/Node include checks |
| `python-hijack` | 2219 | python | **Yes** | python_library_hijacking |
| `rbash-escape` | 2251 | shell | **No** | no restricted-shell check |
| `redis-unauth` | 2300 | services | **No** | no network service / socket enumeration |
| `root-tcp-service` | 2261 | path | **No** | no network service / socket enumeration |
| `root-udp-service` | 2316 | services | **No** | no network service / socket enumeration |
| `selinux-detect-only` | 2388 | services | **No** | no SELinux check |
| `sgid-secret` | 2231 | sgid | **No** | suid_bins scans SUID only, not SGID |
| `sudo-all` | 2170 | sudo-advanced | **Yes** | sudo_dirty_check (sudo -i) + sudo_list |
| `sudo-ansible` | 2275 | sudo-advanced | **Partial** | sudo_list finds rule; writable hook/script path often outside scanned file list |
| `sudo-awk` | 2212 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-backup` | 2265 | sudo-advanced | **Partial** | sudo_list finds rule; writable hook/script path often outside scanned file list |
| `sudo-base64` | 2281 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-bash` | 2179 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-bash-env` | 2193 | sudo-advanced | **Partial** | sudo_list finds NOPASSWD binary; env_keep vector only checked for LD_PRELOAD |
| `sudo-cat` | 2290 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-chmod` | 2191 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-column` | 2327 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-comm` | 2329 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-composer` | 2247 | sudo-advanced | **Partial** | sudo_list finds rule; writable hook/script path often outside scanned file list |
| `sudo-cp` | 2222 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-csplit` | 2352 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-curl` | 2203 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-cut` | 2282 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-dd` | 2192 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-diff` | 2306 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-dos2unix` | 2400 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-ed` | 2435 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-egrep` | 2398 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-env` | 2210 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-expand` | 2314 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-find` | 2205 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-fmt` | 2328 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-fold` | 2322 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-gem` | 2250 | sudo-advanced | **Partial** | sudo_list finds rule; writable hook/script path often outside scanned file list |
| `sudo-git-hook` | 2244 | sudo-advanced | **Partial** | sudo_list finds rule; writable hook/script path often outside scanned file list |
| `sudo-grep` | 2294 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-group` | 2171 | sudo-advanced | **Partial** | sudo_list finds rule; writable hook/script path often outside scanned file list |
| `sudo-hd` | 2323 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-head` | 2291 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-hexdump` | 2350 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-iconv` | 2354 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-install` | 2198 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-join` | 2351 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-jq` | 2373 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-ld-library-path` | 2183 | sudo-advanced | **Partial** | sudo_list finds NOPASSWD binary; env_keep vector only checked for LD_PRELOAD |
| `sudo-ld-preload` | 2213 | sudo-advanced | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-less` | 2206 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-lua` | 2405 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-more` | 2353 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-mv` | 2196 | sudo | **Partial** | sudo_list finds rule; writable hook/script path often outside scanned file list |
| `sudo-nano` | 2207 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-nl` | 2293 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-noauth` | 2233 | sudo-advanced | **Partial** | sudo_list finds rule; writable hook/script path often outside scanned file list |
| `sudo-node` | 2371 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-nodepath` | 2272 | sudo-advanced | **Partial** | sudo_list finds NOPASSWD binary; env_keep vector only checked for LD_PRELOAD |
| `sudo-npm` | 2252 | sudo-advanced | **Partial** | sudo_list finds rule; writable hook/script path often outside scanned file list |
| `sudo-od` | 2277 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-openssl` | 2283 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-paste` | 2324 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-perl` | 2365 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-perl-exec` | 2279 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-perl5lib` | 2194 | sudo-advanced | **Partial** | sudo_list finds NOPASSWD binary; env_keep vector only checked for LD_PRELOAD |
| `sudo-php` | 2367 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-pip` | 2248 | sudo-advanced | **Partial** | sudo_list finds rule; writable hook/script path often outside scanned file list |
| `sudo-pr` | 2304 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-ps4` | 2254 | sudo-advanced | **Partial** | sudo_list finds NOPASSWD binary; env_keep vector only checked for LD_PRELOAD |
| `sudo-ptx` | 2330 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-python` | 2208 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-pythonpath` | 2173 | sudo-advanced | **Partial** | sudo_list finds NOPASSWD binary; env_keep vector only checked for LD_PRELOAD |
| `sudo-rev` | 2325 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-rsync` | 2376 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-ruby` | 2369 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-rubylib` | 2223 | sudo-advanced | **Partial** | sudo_list finds NOPASSWD binary; env_keep vector only checked for LD_PRELOAD |
| `sudo-runas` | 2234 | sudo-advanced | **Partial** | sudo_list finds rule; writable hook/script path often outside scanned file list |
| `sudo-scp` | 2375 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-sed` | 2197 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-shelopts` | 2255 | sudo-advanced | **Partial** | sudo_list finds NOPASSWD binary; env_keep vector only checked for LD_PRELOAD |
| `sudo-shuf` | 2299 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-sort` | 2303 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-split` | 2348 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-sqlite3` | 2396 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-strings` | 2268 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-tac` | 2326 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-tail` | 2292 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-tar` | 2209 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-tee` | 2221 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-u-hash` | 2363 | sudo-advanced | **Partial** | sudo_list shows rule; CVE-2019-14287 not exploitable on patched sudo |
| `sudo-uniq` | 2305 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-version-detect-only` | 2419 | services | **No** | no sudo -V/CVE check |
| `sudo-vim` | 2211 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-wget` | 2204 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-wildcard-tar` | 2236 | sudo-advanced | **Partial** | sudo_list finds rule; writable hook/script path often outside scanned file list |
| `sudo-writable-script` | 2172 | sudo-advanced | **Partial** | sudo_list finds rule; writable hook/script path often outside scanned file list |
| `sudo-xxd` | 2276 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `sudo-yarn` | 2269 | sudo-advanced | **Partial** | sudo_list finds rule; writable hook/script path often outside scanned file list |
| `sudo-zip` | 2289 | sudo | **Yes** | sudo_list / sudoers + runner sudo -l enrichment |
| `suid-base64` | 2285 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-cat` | 2426 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-chmod` | 2195 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-column` | 2343 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-comm` | 2345 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-cp` | 2199 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-csplit` | 2357 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-curl` | 2370 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-cut` | 2399 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-dd` | 2200 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-diff` | 2425 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-dlopen` | 2242 | suid | **Partial** | suid_bins lists binary; custom system()/exec/dlopen needs strings/objdump heuristics |
| `suid-dos2unix` | 2401 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-ed` | 2436 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-env` | 2202 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-expand` | 2358 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-find` | 2214 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-fmt` | 2344 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-fold` | 2331 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-gawk` | 2201 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-grep` | 2307 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-grep2` | 2427 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-hd` | 2332 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-head` | 2295 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-hexdump` | 2355 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-iconv` | 2359 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-install` | 2434 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-install2` | 2453 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-join` | 2356 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-jq` | 2374 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-less` | 2452 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-lua` | 2406 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-more` | 2286 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-nl` | 2309 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-node` | 2372 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-od` | 2402 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-openssl` | 2429 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-paste` | 2335 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-path-hijack` | 2224 | suid | **Partial** | suid_bins lists binary; custom system()/exec/dlopen needs strings/objdump heuristics |
| `suid-perl` | 2366 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-php` | 2368 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-pr` | 2340 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-ptx` | 2347 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-python` | 2215 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-rev` | 2333 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-rsync` | 2377 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-sed` | 2432 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-shuf` | 2430 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-sort` | 2308 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-split` | 2403 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-sqlite3` | 2397 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-strings` | 2404 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-strings2` | 2433 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-tac` | 2334 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-tail` | 2296 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-uniq` | 2341 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-writable` | 2176 | suid | **Partial** | suid_bins lists binary; custom system()/exec/dlopen needs strings/objdump heuristics |
| `suid-writable-exec` | 2225 | suid | **Partial** | suid_bins lists binary; custom system()/exec/dlopen needs strings/objdump heuristics |
| `suid-xxd` | 2428 | suid | **Yes** | suid_bins + GTFOBins |
| `suid-zip` | 2431 | suid | **Yes** | suid_bins + GTFOBins |
| `wildcard-cron` | 2226 | writable | **Partial** | file_permissions — writable dir referenced from cron; may surface via cron.d walk |
| `writable-anacrontab` | 2270 | writable | **Yes** | file_permissions (/etc/anacrontab) |
| `writable-apache-config` | 2278 | writable | **Partial** | file_permissions walks /etc/apache2/apache2.conf only |
| `writable-bashrc` | 2190 | writable | **No** | file_permissions — /root/.bashrc not in scanned paths |
| `writable-cron-allow` | 2249 | writable | **Partial** | file_permissions — path may be outside BeRoot hardcoded list |
| `writable-cron-d` | 2256 | writable | **Yes** | file_permissions (/etc/cron.d) |
| `writable-cron-ref` | 2186 | writable | **Yes** | file_permissions (/etc/crontab → writable script ref) |
| `writable-crontab` | 2216 | writable | **Yes** | file_permissions (/etc/cron.d → writable script ref) |
| `writable-crontab-system` | 2271 | writable | **Yes** | file_permissions (/etc/crontab) |
| `writable-environment` | 2437 | writable | **No** | file_permissions — /etc/environment not in scanned paths |
| `writable-etc-hosts` | 2336 | writable | **No** | file_permissions — /etc/hosts not in scanned paths |
| `writable-exports` | 2187 | nfs | **Yes** | nfs_root_squashing (/etc/exports writable) |
| `writable-init-d` | 2253 | writable | **Partial** | file_permissions — path may be outside BeRoot hardcoded list |
| `writable-ld-so-conf` | 2235 | writable | **No** | file_permissions — /etc/ld.so.conf.d not scanned (only /etc/ld.so.conf file) |
| `writable-ld-so-preload` | 2182 | writable | **No** | file_permissions — /etc/ld.so.preload not in scanned paths |
| `writable-lib` | 2237 | writable | **No** | file_permissions — /usr/local/lib not scanned (only /usr/lib, /lib) |
| `writable-logrotate-d` | 2338 | writable | **No** | file_permissions — logrotate.d not in scanned paths |
| `writable-motd` | 2243 | writable | **No** | file_permissions — /etc/update-motd.d not scanned |
| `writable-nginx-config` | 2284 | writable | **No** | file_permissions — nginx conf.d not in scanned paths |
| `writable-pam` | 2258 | writable | **No** | file_permissions — PAM configs not in scanned paths |
| `writable-passwd` | 2217 | writable | **Yes** | file_permissions (/etc/passwd) |
| `writable-profile` | 2188 | writable | **No** | file_permissions — /etc/profile.d not in scanned paths |
| `writable-rc-local` | 2264 | writable | **No** | file_permissions — /etc/rc.local not in scanned paths |
| `writable-root-ssh` | 2229 | writable | **No** | file_permissions — /root/.ssh not in scanned paths |
| `writable-rsyslog` | 2337 | writable | **No** | file_permissions — rsyslog.d not in scanned paths |
| `writable-shadow` | 2174 | writable | **Yes** | file_permissions (/etc/shadow) |
| `writable-shm-hook` | 2386 | writable | **No** | file_permissions — /dev/shm hook not in scanned paths |
| `writable-sshd-config` | 2257 | writable | **No** | file_permissions — sshd drop-ins not in scanned paths |
| `writable-sudoers` | 2175 | writable | **No** | file_permissions — pending file under /opt/bench, not /etc/sudoers |
| `writable-supervisor` | 2311 | writable | **No** | file_permissions — supervisor conf.d not in scanned paths |
| `writable-systemd-dropin` | 2313 | writable | **No** | file_permissions — systemd drop-ins not scanned (services_files needs dbus) |
| `writable-tmp-hook` | 2395 | writable | **No** | file_permissions — /tmp hook not in scanned paths |
| `writable-udev-rules` | 2312 | writable | **No** | file_permissions — udev rules.d not in scanned paths |
| `writable-vpn-hook` | 2266 | writable | **No** | file_permissions — VPN hook scripts not in scanned paths |
| `writable-webroot` | 2262 | writable | **No** | file_permissions — webroot not in scanned paths |
