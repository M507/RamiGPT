# RamiGPT

**RamiGPT** is an AI-powered offensive security agent designed to pwn root accounts. Leveraging [PwnTools](http://github.com/Gallopsled/pwntools) and OpwnAI capabilities, RamiGPT navigated the privilege escalation scenarios of several systems from [VulnHub](https://www.vulnhub.com/), getting root access in less than a minute.


---

## Collaborative benchmark results

**Live stats only** — the section below is rebuilt from real runs under [`data/benchmark/results/`](data/benchmark/results/) (per-run `result.json` sheets + [`master.json`](data/benchmark/results/master.json)). Commit updated sheets when you want to share results with the team (no automatic git actions).

Per-scenario breakdown (profile · role · target · tools) and the same overall/profile tables also live in [`benchmark.md`](benchmark.md).

**How collaborative merge works:** each run is a sheet under `data/benchmark/results/`. When the master is rebuilt, runs **merge into the same stats** when they share:

- **Model `key_name`** — weights + modelfile params (registry under [`data/benchmark/models/`](data/benchmark/models/))
- **Hardware lab profile** — `BENCHMARK_GPU_*` in `.env` (GPU name, VRAM MiB, driver, CUDA)
- **Scenario** — role, target, and tools

`BENCHMARK_GPU_POWER_LIMIT` is recorded on each run sheet but does **not** affect merge keys (same GPU lab profile merges even if watt cap differs).

**What counts toward pass rate:** only **root achieved** and **wall-clock timeouts**. Aborts like `ai_provider_error`, `max_requests`, tool upload failures, and other infra/setup errors are recorded but excluded from pass rate and timing averages.

The visible **profile** label is `key_name · GPU · VRAM · …`. Same profile + scenario → merged stats. Different model config or GPU lab → separate profile row.

Sample file formats (not merged into the live master): [`data/benchmark/examples/`](data/benchmark/examples/).

<!-- benchmark-master:start -->
_Last updated: 2026-07-28T11:41:55.791888+00:00 · 29 run(s) · [full JSON](data/benchmark/results/master.json)_

**Catalog:** 9 model key(s), 9 profile(s) (model + hardware), 1 role(s), 285 target(s), 1 tool(s), 1 hardware profile(s)

_Identity: **model `key_name`** = weights + modelfile params (registry). **Profile** = model `key_name` · GPU lab (`BENCHMARK_GPU_*`). Runs merge when profile + role + target + tools all match._

#### Overall — openwebui-deepseek-r1-14b · Online AI Service

| Metric | Value |
|--------|------:|
| Observations | 44 |
| Runs | 4 |
| Pass rate (attempted) | 21.4% |
| Got root rate | 21.9% |
| Got root count | 9 |
| Median elapsed (s) | 201.089 |
| Mean elapsed (s) | 261.654 |
| Mean tokens to root | 4,705 |
| Median tokens to root | 4,953 |
| Mean elapsed to root (s) | 488.119 |
| Mean AI requests to root | 1.222 |
| Mean commands to root | 1.111 |
| Tokens/sec to root | 9.640 |

#### Overall — openwebui-openai-gpt-3.5-turbo-latest · Online AI Service

| Metric | Value |
|--------|------:|
| Observations | 114 |
| Runs | 10 |
| Pass rate (attempted) | 63.8% |
| Got root rate | 63.8% |
| Got root count | 30 |
| Median elapsed (s) | 118.756 |
| Mean elapsed (s) | 110.795 |
| Mean tokens to root | 0 |
| Median tokens to root | 0 |
| Mean elapsed to root (s) | 70.938 |
| Mean AI requests to root | 7.433 |
| Mean commands to root | 6.000 |
| Tokens/sec to root | 0.000 |

#### Overall — openwebui-openai-gpt-4-turbo-latest · Online AI Service

| Metric | Value |
|--------|------:|
| Observations | 59 |
| Runs | 3 |
| Pass rate (attempted) | 31.2% |
| Got root rate | 33.3% |
| Got root count | 5 |
| Median elapsed (s) | 181.183 |
| Mean elapsed (s) | 134.288 |
| Mean tokens to root | 0 |
| Median tokens to root | 0 |
| Mean elapsed to root (s) | 31.030 |
| Mean AI requests to root | 5.400 |
| Mean commands to root | 4.400 |
| Tokens/sec to root | 0.000 |

#### Overall — openwebui-openai-gpt-4o-latest · Online AI Service

| Metric | Value |
|--------|------:|
| Observations | 19 |
| Runs | 1 |
| Pass rate (attempted) | 100.0% |
| Got root rate | 100.0% |
| Got root count | 6 |
| Median elapsed (s) | 6.762 |
| Mean elapsed (s) | 25.125 |
| Mean tokens to root | 0 |
| Median tokens to root | 0 |
| Mean elapsed to root (s) | 25.125 |
| Mean AI requests to root | 4.667 |
| Mean commands to root | 1.667 |
| Tokens/sec to root | 0.000 |

#### Overall — openwebui-openai-gpt-4o-mini-latest · Online AI Service

| Metric | Value |
|--------|------:|
| Observations | 57 |
| Runs | 3 |
| Pass rate (attempted) | — |
| Got root rate | — |
| Got root count | 0 |
| Median elapsed (s) | — |
| Mean elapsed (s) | — |
| Mean tokens to root | — |
| Median tokens to root | — |
| Mean elapsed to root (s) | — |
| Mean AI requests to root | — |
| Mean commands to root | — |
| Tokens/sec to root | — |

#### Overall — openwebui-openai-gpt-5-latest · Online AI Service

| Metric | Value |
|--------|------:|
| Observations | 19 |
| Runs | 1 |
| Pass rate (attempted) | 18.2% |
| Got root rate | 18.2% |
| Got root count | 2 |
| Median elapsed (s) | 181.075 |
| Mean elapsed (s) | 167.594 |
| Mean tokens to root | 0 |
| Median tokens to root | 0 |
| Mean elapsed to root (s) | 106.891 |
| Mean AI requests to root | 1.500 |
| Mean commands to root | 1.000 |
| Tokens/sec to root | 0.000 |

#### Overall — openwebui-openai-gpt-5-mini-latest · Online AI Service

| Metric | Value |
|--------|------:|
| Observations | 19 |
| Runs | 1 |
| Pass rate (attempted) | 0.0% |
| Got root rate | 0.0% |
| Got root count | 0 |
| Median elapsed (s) | 181.084 |
| Mean elapsed (s) | 181.105 |
| Mean tokens to root | — |
| Median tokens to root | — |
| Mean elapsed to root (s) | — |
| Mean AI requests to root | — |
| Mean commands to root | — |
| Tokens/sec to root | — |

#### Overall — openwebui-openai-gpt-5.2-latest · Online AI Service

| Metric | Value |
|--------|------:|
| Observations | 326 |
| Runs | 4 |
| Pass rate (attempted) | 24.9% |
| Got root rate | 25.0% |
| Got root count | 60 |
| Median elapsed (s) | 181.209 |
| Mean elapsed (s) | 153.241 |
| Mean tokens to root | 0 |
| Median tokens to root | 0 |
| Mean elapsed to root (s) | 68.189 |
| Mean AI requests to root | 6.317 |
| Mean commands to root | 2.983 |
| Tokens/sec to root | 0.000 |

#### Overall — openwebui-qwen3-14b · Online AI Service

| Metric | Value |
|--------|------:|
| Observations | 38 |
| Runs | 2 |
| Pass rate (attempted) | 5.6% |
| Got root rate | 6.1% |
| Got root count | 2 |
| Median elapsed (s) | 201.096 |
| Mean elapsed (s) | 197.625 |
| Mean tokens to root | 5,145 |
| Median tokens to root | 5,145 |
| Mean elapsed to root (s) | 138.554 |
| Mean AI requests to root | 1.000 |
| Mean commands to root | 1.000 |
| Tokens/sec to root | 37.134 |

#### Profiles

| Profile | n | Pass | Got root | Median (s) | Tokens→root | Elapsed→root (s) | AI req→root |
|---------|--:|-----:|---------:|-----------:|------------:|-----------------:|------------:|
| openwebui-openai-gpt-4o-latest · Online AI Service | 19 | 100.0% | 100.0% | 6.762 | 0 | 25.125 | 4.667 |
| openwebui-openai-gpt-3.5-turbo-latest · Online AI Service | 114 | 63.8% | 63.8% | 118.756 | 0 | 70.938 | 7.433 |
| openwebui-openai-gpt-4-turbo-latest · Online AI Service | 59 | 31.2% | 33.3% | 181.183 | 0 | 31.030 | 5.400 |
| openwebui-openai-gpt-5.2-latest · Online AI Service | 326 | 24.9% | 25.0% | 181.209 | 0 | 68.189 | 6.317 |
| openwebui-deepseek-r1-14b · Online AI Service | 44 | 21.4% | 21.9% | 201.089 | 4,705 | 488.119 | 1.222 |
| openwebui-openai-gpt-5-latest · Online AI Service | 19 | 18.2% | 18.2% | 181.075 | 0 | 106.891 | 1.500 |
| openwebui-qwen3-14b · Online AI Service | 38 | 5.6% | 6.1% | 201.096 | 5,145 | 138.554 | 1.000 |
| openwebui-openai-gpt-5-mini-latest · Online AI Service | 19 | 0.0% | 0.0% | 181.084 | — | — | — |
| openwebui-openai-gpt-4o-mini-latest · Online AI Service | 57 | — | — | — | — | — | — |

#### Most token-efficient profiles (lowest mean tokens to root)

| Profile | Tokens→root | Got root | n |
|---------|------------:|---------:|--:|
| openwebui-openai-gpt-3.5-turbo-latest · Online AI Service | 0 | 63.8% | 114 |
| openwebui-openai-gpt-4-turbo-latest · Online AI Service | 0 | 33.3% | 59 |
| openwebui-openai-gpt-4o-latest · Online AI Service | 0 | 100.0% | 19 |
| openwebui-openai-gpt-5-latest · Online AI Service | 0 | 18.2% | 19 |
| openwebui-openai-gpt-5.2-latest · Online AI Service | 0 | 25.0% | 326 |
| openwebui-deepseek-r1-14b · Online AI Service | 4,705 | 21.9% | 44 |
| openwebui-qwen3-14b · Online AI Service | 5,145 | 6.1% | 38 |

<!-- benchmark-master:end -->

---

![RamiGPT Full AI loop](docs/screenshots/execution_flow.svg)

The diagram above shows the **Full AI** loop: RamiGPT builds a privilege-escalation prompt from session context, asks the configured provider for the next shell command, runs it over SSH, feeds the output back into history, and repeats until root is detected or the request budget is exhausted.

---

## Web workspace

RamiGPT opens into a **multi-session workspace** — a sidebar inventory plus a server workspace for each SSH target. Create sessions, connect when ready, then use the **Terminal** tab for interactive shells and AI tools.

![RamiGPT workspace — landing view with session inventory and quick actions](docs/screenshots/workspace_landing.png)

| Area | What it does |
|------|----------------|
| **Sidebar** | Favorites, recent sessions, and draggable groups (Production, Staging, Benchmark, …). |
| **Session workspace** | Connect / disconnect, terminal I/O, Facts / Hints / Avoid queues, and the Full AI panel. |
| **Top bar** | Search, **Benchmark**, **New Session**, **AI Settings**, **App Settings**, and log cleanup. |

### Typical workflow

1. **Configure AI** — top bar → robot icon (**AI Settings**). Pick a provider, model, and max Full AI requests.
2. **Create or select a session** — **New Session** or click an entry in the sidebar. Credentials are remembered per `user@host:port`.
3. **Connect** — open the session and click **Connect**. Output streams in the Terminal tab.
4. **Run Full AI** — click **Full AI** to start the autonomous priv-esc loop, or pick **BeRoot** / **LinPEAS** from the tool dropdown (optionally with the **AI** checkbox to chain into Full AI).
5. **Guide the model** — add Facts, Hints, or Avoid entries in the right-hand panel; use **Import** / **Export** to share prompt context across sessions.

![RamiGPT terminal — connected session with Full AI and enumeration tools](docs/screenshots/terminal_session.png)

---

## Configuration: AI Providers

RamiGPT supports multiple AI backends. Configure them through the **Settings**
button (robot icon). API keys come from `.env`; provider, model, URL, and UI choices are
saved in `data/ai_settings.json`.

![AI Settings — provider, model, and connection test](docs/screenshots/ai_settings.png)

### Supported providers

| Provider | `AI_PROVIDER` value | Notes |
|----------|---------------------|-------|
| Ollama | `ollama` (default) | Native Ollama OpenAI-compatible API |
| Open WebUI | `openwebui` | Open WebUI OpenAI-compatible API |
| OpenAI | `openai` | Official OpenAI Chat Completions API |

### Quick setup

1. **Copy the example env file:**
   ```sh
   cp .env.example .env
   ```

2. **Ollama** — point at your Ollama host (OpenAI-compatible `/v1`):
   ```
   AI_PROVIDER=ollama
   OLLAMA_BASE_URL=http://127.0.0.1:11434
   OLLAMA_API_KEY=ollama
   OLLAMA_MODEL=qwen3:8b
   ```

3. **Open WebUI** — point at your instance (`/api`):
   ```
   AI_PROVIDER=openwebui
   OPENWEBUI_BASE_URL=http://localhost:3000
   OPENWEBUI_API_KEY=your_openwebui_token
   OPENWEBUI_MODEL=llama3.1
   ```

4. **OpenAI** — set your key (and optionally the model):
   ```
   AI_PROVIDER=openai
   OPENAI_API_KEY=your_api_key_here
   OPENAI_MODEL=gpt-5-mini
   ```

5. **Cursor API** — set your Cursor API key (and optionally the model):
   ```
   AI_PROVIDER=cursor
   CURSOR_API_KEY=your_cursor_api_key
   CURSOR_MODEL=composer-2.5
   ```

6. In the running app, click **AI Settings** to change provider, model, keys, and
   max AI requests. Saving writes non-secret choices to
   `data/ai_settings.json` and API keys to `.env`. **Reload from disk** reloads
   both files. Use **Test connection** to verify the active provider before a benchmark or Full AI run.

### App settings

**App Settings** (sliders icon) control runtime behavior saved alongside provider choices in `data/ai_settings.json`:

![App Settings — role objectives, Session v2, and AI history options](docs/screenshots/app_settings.png)

| Setting | Purpose |
|---------|---------|
| **Role / objective** | Starting persona for prompts (from `ramigpt/config/role_objectives.json`). |
| **Rotate role every prompt** | Cycle through all JSON roles across Full AI turns. |
| **Upgraded Session v2** | Better command extraction and PTY handling (password prompts, editors, nested shells). |
| **Show AI prompts in terminal** | Print `[DEBUG] About to send prompt:` before each AI request. |
| **Include command outputs in AI history** | Send selected shell output back to the model (not just prior commands). |
| **Terminal tools** | Show or hide BeRoot / LinPEAS / LinEnum in the Terminal dropdown. |

### Obtaining an OpenAI API Key

1. Visit [OpenAI](https://www.openai.com/) and sign up / log in.
2. Create an API key in the API dashboard.
3. Put it in `.env` as `OPENAI_API_KEY`, or paste it in the Settings window.

### Ollama notes

- Base URL is the Ollama host (e.g. `http://127.0.0.1:11434`); RamiGPT appends `/v1`.
- Model names must match `ollama list` on that host.
- Use the refresh icon in **AI Settings** to pull the live model list from the host.

### Open WebUI notes

- Create an API key in Open WebUI under **Settings → Account**.
- Use the model ID exactly as it appears in Open WebUI (Ollama, OpenAI, or custom models).
- Base URL should be the Open WebUI origin (e.g. `http://localhost:3000`); RamiGPT appends `/api` for the compatible completions endpoint.


## Run with Docker

### Prerequisites

Before running the project, ensure you have installed:

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)
- An AI backend (OpenAI key, Ollama host, Open WebUI, or Cursor API key)

### Setup

Clone the repository and launch the Docker containers:

```sh
git clone https://github.com/M507/RamiGPT.git
cd RamiGPT
cp .env.example .env   # edit with your provider + keys
docker compose -f docker/docker-compose.yml up -d
```

Access the application at: [https://127.0.0.1:8443](https://127.0.0.1:8443)

Set `APP_RELOAD=0` in `.env` for Docker so the container does not watch source files for reload.

## Run Locally

### Prerequisites

Ensure the following are installed:

- Python 3 and pip
- An AI backend (Ollama, Open WebUI, OpenAI, or Cursor API)
- `ansible-core` 2.18–2.19 (via `requirements.txt`; supports Python 3.8 on remote lab hosts such as Ubuntu 20.04)
- Ubuntu/Debian host packages (auto-installed on startup / first benchmark deploy): `openssh-client`, `sshpass`, `openssl`, `ca-certificates`
  - Or run once: `python3 scripts/ensure_ubuntu_requirements.py`

### Setup

Clone the repository and prepare the environment:

```sh
git clone https://github.com/M507/RamiGPT.git
cd RamiGPT

python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

chmod +x ./scripts/generate_certs.sh
./scripts/generate_certs.sh
pip install -r requirements.txt
cp .env.example .env      # edit provider + API keys
python app.py
```

By default the local server **auto-reloads** when Python, template, or static files change (`APP_RELOAD=1`). Set `APP_RELOAD=0` to disable.

```sh
# optional: turn reload off
APP_RELOAD=0 python app.py
```

The app listens on `127.0.0.1:8443` by default (override with `APP_HOST` / `APP_PORT`).

Access the application at: [https://127.0.0.1:8443](https://127.0.0.1:8443)

TLS certificates are generated under `certs/` by `scripts/generate_certs.sh` (self-signed for local HTTPS).

## Privilege Escalation Benchmark

RamiGPT deploys intentionally misconfigured SSH targets to a **remote lab host** (Ansible) and runs **Full AI** against each until root (or timeout).

![Benchmark modal — remote deploy, model/role plans, and target selection](docs/screenshots/benchmark_modal.png)

### Targets (Docker Compose on remote)

One image (`ramigpt-bench-base`) for all labs; each service only sets `SSH_PORT` + `MISCONFIG` (see `docker/benchmark/apply-misconfig.sh`). Full inventory is in [`docker/benchmark/misconfigs.md`](docker/benchmark/misconfigs.md) and `ramigpt/benchmark/targets.py`. **285** targets, ports **2170–2454** (host networking, no DNAT). Creds: `lowpriv` / `password`.

Deploy uses host networking (`docker/benchmark/docker-compose.yml`) on the remote Linux lab.

```sh
# Prefer: Benchmark UI → Start (Ansible), or:
ansible-playbook -i ansible/benchmark/inventory.example.ini ansible/benchmark/playbook.yml
```

After deploy, confirm each target can obtain root:

```sh
./scripts/benchmark/verify-misconfigs.sh <ip of the testing host where docker will start and can be used for testing and/or benchmarking>
# or: python3 -m ramigpt.benchmark.verify <ip of the testing host where docker will start and can be used for testing and/or benchmarking>
```

UI Benchmark modal → **Test targets (get root)** runs the same probes against the configured remote host.

### From the UI

1. Configure AI (top bar → **AI Settings**).
2. Click **Benchmark**.
3. Set the **remote lab host** (SSH for Ansible; prefills from `data/benchmark/remote.json`).
4. Configure **model plan** and **role plan** (multiple models/roles and runs per target).
5. Pick a **target profile** (default: **Regression sample**, ~19 labs) or use **Select all** for the full suite.
6. Set per-target timeout (default **180s** in the UI).
7. **Start Benchmark** — sessions appear under the **Benchmark** group; Full AI runs on each target in order.

**Target profiles** (22 presets in the **Select from** dropdown): quick runs (*Does it work?*, *Regression sample*, *Easy & portable*), themed runs (*Non-sudo*, *Detect-only*, *Cron & scheduled jobs*, …), and full family buckets (*Classic sudo*, *SUID*, *Credentials*, …). Defined in `ramigpt/benchmark/targets.py` (`PROFILES`). Full integration details: [`docker/benchmark/BENCHMARK_INTEGRATION.md`](docker/benchmark/BENCHMARK_INTEGRATION.md).

### Remote deploy (Ansible)

```sh
# playbook used by the UI:
ansible-playbook -i ansible/benchmark/inventory.example.ini ansible/benchmark/playbook.yml
```


Remote mode from the UI prompts for SSH user/password, installs Docker if needed, copies `docker/benchmark`, brings containers up, and verifies suite SSH ports before Full AI starts.

Requires `ansible-core` 2.18–2.19 (via `requirements.txt`; remote lab Python 3.8+) and Ubuntu host packages (`sshpass`, OpenSSH client, …). On Ubuntu/Debian, RamiGPT installs missing apt packages automatically (`python3 scripts/ensure_ubuntu_requirements.py`, app startup, or first benchmark deploy/verify).

### Bundled enumeration tools

RamiGPT integrates several tools for privilege escalation enumeration:

- **[BeRoot](https://github.com/AlessandroZ/BeRoot)**: Identifies common privilege escalation vectors on Linux (sudo, SUID, capabilities, writable paths, and more).
- **[LinPEAS](https://github.com/carlospolop/PEASS-ng/tree/master/linPEAS)**: Audits Linux environments for misconfigurations and vulnerabilities.
- **LinEnum**: Lightweight enumeration script (uploaded and run like BeRoot).

Run them from the Terminal tool dropdown. With the **AI** checkbox enabled, RamiGPT uploads the tool, captures output, and chains into **Full AI** using the findings.

![BeRoot + Full AI — enumeration output feeding the autonomous loop](docs/screenshots/beroot_full_ai.png)

## Project layout

Application code lives under `ramigpt/`. The repo root stays thin: `app.py` (entrypoint), `requirements.txt`, and `docker/`.

| Path | Role |
|------|------|
| `ramigpt/web/` | Flask/Socket.IO UI, routes, shell layer, Full AI hooks |
| `ramigpt/ai/` | AI provider interface (Ollama, Open WebUI, OpenAI, Cursor) |
| `ramigpt/domain/` | Privilege-escalation prompt + root detection |
| `ramigpt/config/` | Settings from `.env` secrets plus JSON user choices |
| `ramigpt/benchmark/` | Benchmark orchestrator (remote Ansible deploy + Full AI runs) |
| `ramigpt/utils/` | Shared helpers and logging |
| `tools/` | Bundled priv-esc tooling (BeRoot, LinPEAS) |
| `scripts/` | Ops helpers (TLS cert generation, benchmark verify) |
| `docs/` | Screenshots and documentation assets |
| `tests/` | Automated tests |
| `docker/benchmark/` | One-image LPE labs (`MISCONFIG` profiles; ports 2170–2454). Guide: [`docker/benchmark/BENCHMARK_INTEGRATION.md`](docker/benchmark/BENCHMARK_INTEGRATION.md) |
| `ansible/benchmark/` | Ansible playbook to deploy targets on a remote host |
| `data/` | Runtime logs, sessions, and benchmark results (gitignored except committed benchmark sheets) |
| `data/sessions/hosts/` | One JSON file per saved SSH session/host |
| `data/sessions/meta.json` | Groups + recent session ids |
| `certs/` | TLS certificates (gitignored) |

## Features

### Session context (Facts, Hints, Avoid)

Per-session queues in the Terminal AI panel steer Full AI without editing `.env`:

- **Facts** — ground truth the model should treat as established (e.g. kernel version, discovered SUID binaries).
- **Hints** — suggested directions without guaranteeing success.
- **Avoid** — commands or approaches that already failed.

Use **Import** / **Export** to move this context between sessions or capture it for write-ups and flags.

### Full AI autonomous loop

**Full AI** runs a background loop: build prompt → ask provider → execute one shell command → append to history → check for root → repeat. **Stop** halts the loop; **Guide Me** sends a single AI turn without starting the full autonomous run.

Session v2 (enabled in **App Settings**) improves command extraction and handles interactive edge cases — sudo password prompts, stuck editors, and nested root shells.

### AI provider settings

Switch between **Ollama**, **Open WebUI**, **OpenAI**, and **Cursor API** from
the **AI Settings** button. The selection persists in `data/ai_settings.json`;
`.env` remains the source for API keys and initial defaults.

## Disclaimer

RamiGPT is intended solely for **educational and authorized security testing**. Use it responsibly and only on systems where you have explicit permission to conduct tests.

