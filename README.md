# RamiGPT

**RamiGPT** is an AI-powered offensive security agent designed to pwn root accounts. Leveraging [PwnTools](http://github.com/Gallopsled/pwntools) and LLM capabilities, RamiGPT navigated the privilege escalation scenarios of several systems from [VulnHub](https://www.vulnhub.com/) and custom-built test causes, getting root access and documenting the results below.


---

## Collaborative benchmark results


<!-- benchmark-master:start -->
_Last updated: 2026-07-29T19:08:55.634015+00:00 · 62 run(s) · [full JSON](data/benchmark/results/master.json)_

#### Profiles

| Profile | n | Pass | Got root | Median (s) | Tokens→root | Elapsed→root (s) | AI req→root |
|---------|--:|-----:|---------:|-----------:|------------:|-----------------:|------------:|
| openwebui-openai-gpt-3.5-turbo-latest · Online AI Service | 153 | 50.0% | 50.6% | 84.042 | 0 | 65.773 | 7.095 |
| openrouter-deepseek-deepseek-v4-flash · Online AI Service | 39 | 43.2% | 45.7% | 181.061 | 6,728 | 55.688 | 4.000 |
| openrouter-deepseek-deepseek-v3.2 · Online AI Service | 42 | 39.4% | 50.0% | 119.552 | 5,149 | 40.721 | 4.923 |
| openwebui-openai-gpt-4o-latest · Online AI Service | 38 | 31.4% | 31.4% | 44.519 | 0 | 27.955 | 4.182 |
| openwebui-openai-gpt-4-turbo-latest · Online AI Service | 59 | 31.2% | 33.3% | 181.183 | 0 | 31.030 | 5.400 |
| openwebui-openai-gpt-5-latest · Online AI Service | 58 | 25.0% | 25.8% | 61.037 | 0 | 64.496 | 1.375 |
| openwebui-openai-gpt-5.2-latest · Online AI Service | 326 | 23.5% | 23.6% | 181.185 | 0 | 68.189 | 6.317 |
| openwebui-deepseek-r1-14b · Online AI Service | 171 | 17.3% | 17.7% | 181.137 | 4,391 | 212.419 | 1.536 |
| openwebui-qwen3-14b · Online AI Service | 164 | 3.2% | 3.5% | 181.267 | 5,655 | 146.442 | 1.400 |
| openwebui-openai-gpt-5-mini-latest · Online AI Service | 19 | 0.0% | 0.0% | 181.070 | — | — | — |
| openrouter-openai-gpt-4o · Online AI Service | 1 | — | — | — | — | — | — |
| openwebui-openai-gpt-4o-mini-latest · Online AI Service | 57 | — | — | — | — | — | — |

#### Most token-efficient profiles (lowest mean tokens to root)

| Profile | Tokens→root | Got root | n |
|---------|------------:|---------:|--:|
| openwebui-deepseek-r1-14b · Online AI Service | 4,391 | 17.7% | 171 |
| openrouter-deepseek-deepseek-v3.2 · Online AI Service | 5,149 | 50.0% | 42 |
| openwebui-qwen3-14b · Online AI Service | 5,655 | 3.5% | 164 |
| openrouter-deepseek-deepseek-v4-flash · Online AI Service | 6,728 | 45.7% | 39 |
| openwebui-openai-gpt-3.5-turbo-latest · Online AI Service | 0 | 50.6% | 153 |
| openwebui-openai-gpt-4-turbo-latest · Online AI Service | 0 | 33.3% | 59 |
| openwebui-openai-gpt-4o-latest · Online AI Service | 0 | 31.4% | 38 |
| openwebui-openai-gpt-5-latest · Online AI Service | 0 | 25.8% | 58 |

<!-- benchmark-master:end -->

**Live stats only** — the tables above are rebuilt from real runs under [`data/benchmark/results/`](data/benchmark/results/) (per-run `result.json` sheets + [`master.json`](data/benchmark/results/master.json)). Commit updated sheets when you want to share results with the team (no automatic git actions).

Per-scenario breakdown (profile · role · target · tools) and the same overall/profile tables also live in [`benchmark.md`](benchmark.md).

**How collaborative merge works:** each run is a sheet under `data/benchmark/results/`. When the master is rebuilt, runs **merge into the same stats** when they share:

- **Model `key_name`** — weights + modelfile params (registry under [`data/benchmark/models/`](data/benchmark/models/))
- **Hardware lab profile** — `BENCHMARK_GPU_*` in `.env` (GPU name, VRAM MiB, driver, CUDA)
- **Scenario** — role, target, and tools

`BENCHMARK_GPU_POWER_LIMIT` is recorded on each run sheet but does **not** affect merge keys (same GPU lab profile merges even if watt cap differs).

**What counts toward pass rate:** **root achieved**, **wall-clock timeouts**, and **request-budget exhaustion** (`max_requests`). Infra/provider aborts like `ai_provider_error`, tool upload failures, reconnect exhaustion, and other setup errors are recorded but excluded from pass rate and timing averages.

The visible **profile** label is `key_name · GPU · VRAM · …`. Same profile + scenario → merged stats. Different model config or GPU lab → separate profile row.

Sample file formats (not merged into the live master): [`data/benchmark/examples/`](data/benchmark/examples/).

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
| OpenRouter | `openrouter` | Official OpenRouter SDK (multi-model gateway) |
| Cursor | `cursor` | Cursor Cloud Agents API |

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

5. **OpenRouter** — set your OpenRouter key (and optionally the model):
   ```
   AI_PROVIDER=openrouter
   OPENROUTER_API_KEY=your_openrouter_api_key
   OPENROUTER_MODEL=openai/gpt-4o-mini
   ```

6. **Cursor API** — set your Cursor API key (and optionally the model):
   ```
   AI_PROVIDER=cursor
   CURSOR_API_KEY=your_cursor_api_key
   CURSOR_MODEL=composer-2.5
   ```

7. In the running app, click **AI Settings** to change provider, model, keys, and
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

### OpenRouter notes

- Create an API key at [openrouter.ai/keys](https://openrouter.ai/keys).
- Model IDs use the `provider/model` form (e.g. `openai/gpt-4o-mini`, `anthropic/claude-sonnet-4`).
- Uses the official `openrouter` Python SDK; leave `OPENROUTER_BASE_URL` empty for `https://openrouter.ai/api/v1`.
- Use the refresh icon in **AI Settings** to pull the live model catalog.


## Run with Docker

### Prerequisites

Before running the project, ensure you have installed:

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)
- An AI backend (OpenAI key, Ollama host, Open WebUI, OpenRouter, or Cursor API key)

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
- An AI backend (Ollama, Open WebUI, OpenAI, OpenRouter, or Cursor API)
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

**Getting started (screenshots):** [`docs/how-to-start-benchmarking.md`](docs/how-to-start-benchmarking.md) · suite details: [`benchmark.md`](benchmark.md) · integration: [`docker/benchmark/BENCHMARK_INTEGRATION.md`](docker/benchmark/BENCHMARK_INTEGRATION.md)

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

![Collaborative benchmark leaderboard](docs/screenshots/benchmark_leaderboard.png)

## Project layout

Application code lives under `ramigpt/`. The repo root stays thin: `app.py` (entrypoint), `requirements.txt`, and `docker/`.

| Path | Role |
|------|------|
| `ramigpt/web/` | Flask/Socket.IO UI, routes, shell layer, Full AI hooks |
| `ramigpt/ai/` | AI provider interface (Ollama, Open WebUI, OpenAI, OpenRouter, Cursor) |
| `ramigpt/domain/` | Privilege-escalation prompt + root detection |
| `ramigpt/config/` | Settings from `.env` secrets plus JSON user choices |
| `ramigpt/benchmark/` | Benchmark orchestrator (remote Ansible deploy + Full AI runs) |
| `ramigpt/utils/` | Shared helpers and logging |
| `tools/` | Bundled priv-esc tooling (BeRoot, LinPEAS) |
| `scripts/` | Ops helpers (TLS cert generation, benchmark verify) |
| `docs/` | Screenshots and guides (e.g. [`how-to-start-benchmarking.md`](docs/how-to-start-benchmarking.md)) |
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

Switch between **Ollama**, **Open WebUI**, **OpenAI**, **OpenRouter**, and **Cursor API** from
the **AI Settings** button. The selection persists in `data/ai_settings.json`;
`.env` remains the source for API keys and initial defaults.

## Disclaimer

RamiGPT is intended solely for **educational and authorized security testing**. Use it responsibly and only on systems where you have explicit permission to conduct tests.

