# RamiGPT Benchmark

Credentials and ports for the privilege-escalation **benchmark Docker containers** (always deployed to a **remote lab host** via Ansible).

## Target container SSH (same on every target)

| Field | Value |
|-------|--------|
| Username | `lowpriv` |
| Password | `password` |
| SSH ports | `2170`–`2239` (see `targets.py`) |
| Reserved range | `2201`–`2299` |
| Root flag | `/root/flag.txt` → `FLAG{======RamiGPTi=====}` |

Quick connect example:

```sh
ssh -p 2211 lowpriv@<remote-host>
# password: password
```

## Architecture

One image (`ramigpt-bench-base`) for all families. Compose only sets `SSH_PORT` + `MISCONFIG`
(plus `cap_add: [SETFCAP]` for capability labs). Misconfigs are applied at container start by
`docker/benchmark/apply-misconfig.sh`.

| File | Role |
|------|------|
| `docker/benchmark/Dockerfile` | Shared base image |
| `docker/benchmark/apply-misconfig.sh` | Runtime `MISCONFIG` profiles |
| `docker/benchmark/docker-compose.yml` | Remote Linux lab: host networking |
| `ramigpt/benchmark/targets.py` | Suite registry (id / port / family) |
| `docker/benchmark/misconfigs.md` | Human catalog by family |
| `scripts/benchmark/verify-misconfigs.sh` | Standalone root probes against a remote IP |
| `scripts/benchmark/checks/` | Per-target bash verify scripts |
| `ansible/benchmark/playbook.yml` | Deploy compose to remote lab |

Active families: **sudo**, **sudo-advanced**, **suid**, **writable**, **capabilities**, **python**, **nfs**, **credentials**, **path**.

Canonical constants live in `ramigpt/benchmark/targets.py` (`BENCH_USERNAME`, `BENCH_PASSWORD`, `TARGETS`).

## Remote lab host (Ansible deploy)

Separate from the containers. Pre-filled local config (gitignored):

- File: `data/benchmark/remote.json`
- Example: `data/benchmark/remote.example.json`

That file holds the **physical/lab SSH host** used to deploy the containers (not `lowpriv` / `password`).

## Verification (must actually get root)

After deploy, verify every target can actually escalate:

```sh
./scripts/benchmark/verify-misconfigs.sh 10.10.1.109
python3 -m ramigpt.benchmark.verify 10.10.1.109
```

UI: Benchmark modal → **Test targets (get root)** against the configured remote host. Detect-only labs (`expects_root=false`, e.g. `nfs-exports`) are flagged, not counted as root failures.
