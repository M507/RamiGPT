# RamiGPT

**RamiGPT** is an AI-powered offensive security agent designed to pwn root accounts. Leveraging [PwnTools](http://github.com/Gallopsled/pwntools) and OpwnAI capabilities, RamiGPT navigated the privilege escalation scenarios of several systems from [VulnHub](https://www.vulnhub.com/), getting root access in less than a minute.


## Timing Table

| Task Description | Source | Elapsed Time in Seconds | Model |
|------------------|------------|--------------|-------|
| symfonos5 | https://www.vulnhub.com/entry/symfonos-52,415/ | 50.521 | gpt-5-mini |
| Escalate Linux 1 | https://www.vulnhub.com/entry/escalate_linux-1,323/ | 12.827717 | gpt-3.5-turbo |
| Nyx 1 | https://www.vulnhub.com/entry/nyx-1,535/ | 10.044392 | gpt-3.5-turbo |
| Venom: 1 | https://www.vulnhub.com/entry/venom-1,701/ | 09.669650 | gpt-3.5-turbo |
| digitalworld.local: TORMENT | https://www.vulnhub.com/entry/digitalworldlocal-torment,299/ | 09.729105 | gpt-3.5-turbo |
| digitalworld.local: DEVELOPMENT | https://www.vulnhub.com/entry/digitalworldlocal-development,280/ | 09.911129 | gpt-3.5-turbo |
| Tiki: 1 | https://www.vulnhub.com/entry/tiki-1,525/ | 10.166464 | gpt-3.5-turbo |
| hacksudo: L.P.E. | https://www.vulnhub.com/entry/hacksudo-lpe,698/ | 09.846106 | gpt-3.5-turbo |
| DC: 2 | https://www.vulnhub.com/entry/dc-2,311/ | 09.660332 | gpt-3.5-turbo |
| DevGuru: 1 | https://www.vulnhub.com/entry/devguru-1,620/ | 10.354190 | gpt-3.5-turbo |
| serial: 1 | https://www.vulnhub.com/entry/serial-1,349/ | 09.617828 | gpt-3.5-turbo |
| Dina: 1.0.1 | https://www.vulnhub.com/entry/dina-101,200/ | 09.685389 | gpt-3.5-turbo |
| Autonomous - Hostname:pehost, Server:None, Username:zeus | Link | 10.363169 | gpt-3.5-turbo |
| Autonomous - Hostname:pehost, Server:None, Username:zeus | Link | 09.944443 | gpt-3.5-turbo |
| Autonomous - Hostname:bench-vim, Server:127.0.0.1, Username:zeus | Link | 2026-07-14 17:29:31.446745 | 2026-07-14 17:29:31.779035 | 0:00:00.332290 |

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
| Ollama | `ollama` (default) | Native Ollama OpenAI-compatible API at `/v1/chat/completions` |
| Open WebUI | `openwebui` | Open WebUI OpenAI-compatible API at `/api/chat/completions` |
| OpenAI | `openai` | Official OpenAI Chat Completions API |
| Cursor API | `cursor` | Cursor [Cloud Agents API](https://cursor.com/docs/cloud-agent/api/endpoints) — runs each turn as a no-repo cloud agent, any model listed by `GET /v1/models` |

### Quick setup

1. **Copy the example env file:**
   ```sh
   cp .env.example .env
   ```

2. **Ollama** — point at your Ollama host (OpenAI-compatible `/v1`):
   ```
   AI_PROVIDER=ollama
   OLLAMA_BASE_URL=http://10.10.10.82:11434
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

- Base URL is the Ollama host (e.g. `http://10.10.10.82:11434`); RamiGPT appends `/v1`.
- Model names must match `ollama list` on that host.
- Use the refresh icon in **AI Settings** to pull the live model list from the host.

### Open WebUI notes

- Create an API key in Open WebUI under **Settings → Account**.
- Use the model ID exactly as it appears in Open WebUI (Ollama, OpenAI, or custom models).
- Base URL should be the Open WebUI origin (e.g. `http://localhost:3000`); RamiGPT appends `/api` for the compatible completions endpoint.

### Cursor API notes

- Generate a user API key from the [Cursor Dashboard → API Keys](https://cursor.com/dashboard), or use a service account API key.
- Any model ID accepted by `model.id` on Cloud Agents works (e.g. `composer-2.5`, `claude-sonnet-4-6`, `gpt-5.2`). Click the refresh icon next to the model field in **Settings** to list the current recommended models from `GET /v1/models`, or type a model ID manually. Agent create can take ~60s while Cursor provisions a cloud VM.
- Each pentest turn creates a fresh, repo-less Cloud Agent, waits for it to finish, reads its reply, then archives it — so this provider is noticeably slower per request than the other providers (agent boot + run time vs. a plain chat completion). It never touches a GitHub repo (no `repos`/`env`/PR creation).


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
- `ansible-core` (for Benchmark remote deploy; installed via `requirements.txt`)

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
./scripts/benchmark/verify-misconfigs.sh 10.10.1.109
# or: python3 -m ramigpt.benchmark.verify 10.10.1.109
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

### Collaborative benchmark results

**Live stats only** — the section below is rebuilt from real runs under [`data/benchmark/results/`](data/benchmark/results/) (per-run `result.json` sheets + [`master.json`](data/benchmark/results/master.json)). Commit updated sheets when you want to share results with the team (no automatic git actions).

**How collaborative merge works:** each run is a sheet under `data/benchmark/results/`. When the master is rebuilt, runs **merge into the same stats** when they share:

- **Model `key_name`** — weights + modelfile params (registry under [`data/benchmark/models/`](data/benchmark/models/))
- **Hardware lab profile** — `BENCHMARK_GPU_*` in `.env` (GPU name, VRAM MiB, driver, CUDA)
- **Scenario** — role, target, and tools

`BENCHMARK_GPU_POWER_LIMIT` is recorded on each run sheet but does **not** affect merge keys (same GPU lab profile merges even if watt cap differs).

The visible **profile** label is `key_name · GPU · VRAM · …`. Same profile + scenario → merged stats. Different model config or GPU lab → separate profile row.

Sample file formats (not merged into the live master): [`data/benchmark/examples/`](data/benchmark/examples/).

<!-- benchmark-master:start -->
_Last updated: 2026-07-20T20:58:45.714196+00:00 · 0 run(s) · [full JSON](data/benchmark/results/master.json)_

_No benchmark runs yet._

Run the suite from the **Benchmark** UI to create per-run sheets under `data/benchmark/results/` and populate this section. See [`data/benchmark/examples/`](data/benchmark/examples/) for sample file formats only.

<!-- benchmark-master:end -->

### Remote deploy (Ansible)

```sh
# playbook used by the UI:
ansible-playbook -i ansible/benchmark/inventory.example.ini ansible/benchmark/playbook.yml
```


Remote mode from the UI prompts for SSH user/password, installs Docker if needed, copies `docker/benchmark`, brings containers up, and verifies suite SSH ports before Full AI starts.

Requires `ansible-core` (installed via `requirements.txt`).

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

