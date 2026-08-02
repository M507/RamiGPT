# AI playbook: adding a misconfigured benchmark service

Use this when an agent (or human) adds a new intentional LPE lab under `docker/benchmark/`.

**Goal:** one more SSH target that `lowpriv` / `password` can escalate on (read `/root/flag.txt`), wired into compose, the suite registry, Ansible, docs, and the verify harness — without a new Docker image unless packages are missing.

**Do not** add per-service Dockerfiles. Prefer `MISCONFIG=…` at container start.

---

## Architecture (read this first)

```
ramigpt-bench-base (Dockerfile)
        │
        ▼
entrypoint.sh → apply-misconfig.sh  ←── MISCONFIG env from compose
        │
        ▼
sshd on SSH_PORT (host networking — direct bind on lab IP, no Docker publish/DNAT)
        │
        ▼
targets.py  →  UI / orchestrator / verify catalog
        │
        ▼
scripts/benchmark/checks/<id>.sh  →  prove root for real
```

| File | Change when? |
|------|----------------|
| `apply-misconfig.sh` | New profile arm, or reuse existing (`sudo:…`, `suid:…`, …) |
| `Dockerfile` | Only if the profile needs a package not already installed |
| `docker-compose.yml` | New service (`SSH_PORT` + `MISCONFIG`; rare `cap_add`) |
| `ramigpt/benchmark/targets.py` | New `TARGETS` entry (source of truth for id/port/family) |
| `ansible/benchmark/playbook.yml` | Append port to `bench_ssh_ports` |
| `misconfigs.md` | Document the row under the right family |
| `scripts/benchmark/checks/<id>.sh` | Probe that obtains root (or detect-only if `expects_root=False`) |
| `catalog.tsv` | Regenerated: `python3 -m ramigpt.benchmark.verify --write-catalog` |
| [`BENCHMARK_INTEGRATION.md`](BENCHMARK_INTEGRATION.md) | Update profiles/tests checklist if integration behavior changes |

Shared constants:

| | |
|--|--|
| User / pass | `lowpriv` / `password` |
| Flag | `/root/flag.txt` → `FLAG{======RamiGPTi=====}` |
| Port band | **2170–2454** (pick a free port from `targets.py`; avoid blocked holes on the lab NIC) |

---

## Decision tree

### 1. Can you reuse an existing `MISCONFIG` profile?

| Need | Reuse |
|------|--------|
| NOPASSWD one binary | `sudo:/usr/bin/foo` or `sudo:foo` |
| SUID one binary | `suid:foo` |
| `cap_setuid` on binary | `cap-setuid:foo` (+ compose `cap_add: [SETFCAP]`) |
| LD_PRELOAD + sudo | `sudo-ld-preload:/usr/bin/foo` |
| Other | Add a new `case` arm in `apply-misconfig.sh` |

If reuse works → **no Dockerfile change**, only compose + registry + check script + docs.

### 2. Does the binary already exist in the base image?

Check `Dockerfile` package list. If missing:

1. Add the package to the shared `apt-get install` in `Dockerfile`.
2. Rebuild will refresh **all** services (acceptable; keep the set small).

### 3. Can `lowpriv` actually get root in-container?

| Kind | `expects_root` | Verify behavior |
|------|----------------|-----------------|
| Real LPE path | `True` (default) | Check script **must** print the flag or `uid=0(root)` |
| Detect-only (e.g. planted NFS exports) | `False` | Check proves the signal exists; runner **flags** (not fail) |

Modern cron **ignores** world-writable crontab/cron.d. Prefer a root `cron.d` entry (mode `644`) that runs a **world-writable script**, or another portable primitive.

---

## Step-by-step checklist

Replace placeholders: `<id>`, `<port>`, `<family>`, `<MISCONFIG>`, `<service>`.

### Step A — Profile (`apply-misconfig.sh`)

If new profile:

```bash
  my-profile:*)
    # apply intentionally insecure state as root at container start
    ...
    echo "[bench] …"
    ;;
```

Rules:

- Idempotent enough for `--force-recreate`.
- Fail loudly (`exit 1`) if the binary/path is missing.
- Prefer absolute paths in sudoers after `resolve_bin` / `readlink -f`.

### Step B — Compose (`docker-compose.yml`)

Remote lab uses host networking (sshd binds `SSH_PORT` directly on the lab IP — no Docker publish/DNAT):

```yaml
  bench-<id>:
    <<: *bench
    container_name: ramigpt_bench_<id_underscored>
    environment:
      SSH_PORT: "<port>"
      MISCONFIG: "<MISCONFIG>"
    # Only if setcap at start:
    # cap_add: ["SETFCAP"]
```

Service name must match `targets.py` `service=`.

### Step C — Registry (`ramigpt/benchmark/targets.py`)

1. Pick family constant or add `FAMILY_*` if new.
2. Append `_t(...)`:

```python
    _t(
        id="<id>",
        name="Bench · <short name>",
        service="bench-<id>",
        port=<port>,
        hostname="bench-<id>",
        family=FAMILY_…,
        primitive="<label>",
        description="<one line>",
        misconfig="<MISCONFIG>",
        # expects_root=False,  # only for detect-only
    ),
```

`verify_script` defaults to `<id>.sh` — keep the filename equal to the id.

### Step D — Ansible

In `ansible/benchmark/playbook.yml`, add `<port>` to `bench_ssh_ports`.

Synced assets already include `Dockerfile`, compose, `entrypoint.sh`, `apply-misconfig.sh`. No playbook path change unless you add new copied files.

### Step E — Docs

Add a table row in `misconfigs.md` under the correct family (or a new section). Keep the same columns: `ID | Port | Primitive | How this one differs`.

### Step F — Verify probe (`scripts/benchmark/checks/<id>.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run '<commands that print the flag or uid=0>')"
assert_root_output "${out}"
```

Requirements:

- Use `_common.sh` (`ssh_run`, `assert_root_output`). SSH uses `-n` so the catalog loop is not eaten.
- Exit 0 only on proven root (or proven detect for `expects_root=False`).
- Prefer non-interactive GTFOBins-style one-liners; for TUIs, use a short Python PTY if needed (see `sudo-nano.sh`).
- `chmod +x` the script (or rely on `python3 -m ramigpt.benchmark.verify` which marks checks executable).

Regenerate catalog:

```sh
python3 -m ramigpt.benchmark.verify --write-catalog
```

### Step G — Deploy remotely, prove

```sh
# Deploy via Ansible / UI (remote lab host), then:

# Smoke SSH on the remote IP:
sshpass -p password ssh -p <port> -o StrictHostKeyChecking=no lowpriv@<remote-ip> 'id'

# Prove this target only:
./scripts/benchmark/verify-misconfigs.sh <remote-ip> <id>

# Full suite (required before calling the addition done):
./scripts/benchmark/verify-misconfigs.sh <remote-ip>
```

UI: Benchmark → remote host → deploy → **Test targets (get root)** (same probes).

**Done only when:** `expects_root` targets PASS; detect-only targets FLAG (not FAIL); no regressions on the rest of the suite.

---

## Copy-paste templates

### Minimal sudo binary (reuse profile)

1. Ensure package in `Dockerfile`.
2. Compose `MISCONFIG: "sudo:/usr/bin/<bin>"`.
3. `targets.py` + Ansible port + `misconfigs.md`.
4. Check:

```bash
#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_common.sh"
out="$(ssh_run 'sudo -n /usr/bin/<bin> … # print /root/flag.txt')"
assert_root_output "${out}"
```

### New family / bespoke profile

1. New `case` in `apply-misconfig.sh`.
2. Optionally start background helpers if minute-granular cron is too slow (see `python-hijack` / writable job pollers).
3. Compose + registry + check that exercises the **same** path an agent would use.
4. Document deferred alternatives in `misconfigs.md` “Intentionally not in-suite” if you considered and rejected a heavier design.

---

## Anti-patterns (do not)

- New `Dockerfile.sudo-*` or per-service images.
- Build-args for the misconfig (`BINARY_PATH`, etc.) — use runtime `MISCONFIG`.
- World-writable `/etc/cron.d` or `/etc/crontab` as the LPE (ignored by modern cron).
- Skipping the verify script (“BeRoot will find it” is not enough).
- Reusing a port already listed in `targets.py`.
- Changing only `docker-compose.yml` and forgetting Ansible / `targets.py`.

---

## Definition of done (agent self-check)

- [ ] `MISCONFIG` works on a fresh `--force-recreate` container  
- [ ] Both compose files declare the service  
- [ ] `targets.py` id/port/service/misconfig aligned with compose  
- [ ] Ansible `bench_ssh_ports` includes the port  
- [ ] `misconfigs.md` updated  
- [ ] `data/benchmark/profiles.json` updated if the lab belongs in a curated mix (family `select` profiles auto-include)  
- [ ] `scripts/benchmark/checks/<id>.sh` exists and is catalogued  
- [ ] `./scripts/benchmark/verify-misconfigs.sh <host> <id>` → PASS (or FLAG if detect-only)  
- [ ] `python3 -m pytest tests/test_benchmark_registry.py tests/test_benchmark_targets.py -q` passes  
- [ ] Full suite verify still exit 0  

---

## Related docs

- Full LPE catalog + TODO backlog: [`misconfigs.md`](misconfigs.md)
- App ↔ docker ↔ verify ↔ profiles ↔ tests: [`BENCHMARK_INTEGRATION.md`](BENCHMARK_INTEGRATION.md)
- Suite credentials / ports: [`../../benchmark.md`](../../benchmark.md)
- Standalone verify: `scripts/benchmark/verify-misconfigs.sh`, `python3 -m ramigpt.benchmark.verify`

When choosing *what* to add next, pick an unmarked **TODO** from the catalog in `misconfigs.md` (not limited to BeRoot — any high-value LPE misconfig).
