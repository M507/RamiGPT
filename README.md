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

![image info](docs/screenshots/execution_flow.svg)

---

## GUI:

>![alt text](docs/screenshots/poc_pwn.gif)


## Configuration: AI Providers

RamiGPT supports multiple AI backends. Configure them through the **Settings**
button. API keys come from `.env`; provider, model, URL, and UI choices are
saved in `data/ai_settings.json`.

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

6. In the running app, click **Settings** to change provider, model, keys, and
   max AI requests. Saving writes non-secret choices to
   `data/ai_settings.json` and API keys to `.env`. **Reload from disk** reloads
   both files.

### Obtaining an OpenAI API Key

1. Visit [OpenAI](https://www.openai.com/) and sign up / log in.
2. Create an API key in the API dashboard.
3. Put it in `.env` as `OPENAI_API_KEY`, or paste it in the Settings window.

### Ollama notes

- Base URL is the Ollama host (e.g. `http://10.10.10.82:11434`); RamiGPT appends `/v1`.
- Model names must match `ollama list` on that host.

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
- OpenAI key

### Setup

Clone the repository and launch the Docker containers:

```sh
git clone https://github.com/M507/RamiGPT.git
cd RamiGPT
docker compose -f docker/docker-compose.yml up -d
```

Access the application at: [https://127.0.0.1:8443](https://127.0.0.1:8443)

## Run Locally

### Prerequisites

Ensure the following are installed:

- Python 3 and pip
- OpenAI key (or Open WebUI)

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
python app.py
```

By default the local server **auto-reloads** when Python, template, or static files change (`APP_RELOAD=1`). Set `APP_RELOAD=0` to disable.

```sh
# optional: turn reload off
APP_RELOAD=0 python app.py
```

The app listens on `127.0.0.1:8443` by default (override with `APP_HOST` / `APP_PORT`).

Access the application at: [https://127.0.0.1:8443](https://127.0.0.1:8443)

The app opens into a **multi-session workspace** (sidebar inventory + server workspace). Create sessions, connect when ready, then use the Terminal tab for SSH and RamiGPT AI tools. AI provider settings are available from the top bar gear icon before connecting.

## Privilege Escalation Benchmark

RamiGPT deploys intentionally misconfigured SSH targets to a **remote lab host** (Ansible) and runs **Full AI** against each until root (or timeout).

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

1. Configure AI (top bar → Settings).
2. Click **Benchmark**.
3. Set the **remote lab host** (SSH for Ansible; prefills from `data/benchmark/remote.json`).
4. Pick a **target profile** (default: **Regression sample**, ~19 labs) or use **Select all** for the full suite.
5. Set per-target timeout (default **180s** in the UI).
6. **Start Benchmark** — sessions appear under the **Benchmark** group; Full AI runs on each target in order.

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
_Last updated: 2026-07-19T11:33:19.471144+00:00 · 1 run(s) · [full JSON](data/benchmark/results/master.json)_

**Catalog:** 1 model key(s), 1 profile(s) (model + hardware), 1 role(s), 1 target(s), 1 tool(s), 0 hardware profile(s)

_Identity: **model `key_name`** = weights + modelfile params (registry). **Profile** = model `key_name` · GPU lab (`BENCHMARK_GPU_*`). Runs merge when profile + role + target + tools all match._

#### Overall — ollama/qwen3:14b

| Metric | Value |
|--------|------:|
| Observations | 1 |
| Runs | 1 |
| Pass rate | 100.0% |
| Got root rate | 100.0% |
| Got root count | 1 |
| Median elapsed (s) | 15.000 |
| Mean elapsed (s) | 15.000 |
| Mean tokens to root | 110 |
| Median tokens to root | 110 |
| Mean elapsed to root (s) | 15.000 |
| Mean AI requests to root | 1.000 |
| Mean commands to root | 1.000 |
| Tokens/sec to root | 7.333 |

#### Profiles

| Profile | n | Pass | Got root | Median (s) | Tokens→root | Elapsed→root (s) | AI req→root |
|---------|--:|-----:|---------:|-----------:|------------:|-----------------:|------------:|
| ollama/qwen3:14b | 1 | 100.0% | 100.0% | 15.000 | 110 | 15.000 | 1.000 |

#### Most token-efficient profiles (lowest mean tokens to root)

| Profile | Tokens→root | Got root | n |
|---------|------------:|---------:|--:|
| ollama/qwen3:14b | 110 | 100.0% | 1 |

#### Scenarios (profile · role · target · tools)

| Profile | Role | Target | Tools | n | Pass | Got root | Tokens→root | Elapsed→root (s) | AI req | Commands |
|---------|------|--------|-------|--:|-----:|---------:|------------:|-----------------:|-------:|---------:|
| ollama/qwen3:14b | Direct Privilege Escalation Operator | `sudo-vim` | `beroot` | 1 | 100.0% | 100.0% | 110 | 15.000 | 1.000 | 1.000 |

<!-- benchmark-master:end -->

### Remote deploy (Ansible)

```sh
# playbook used by the UI:
ansible-playbook -i ansible/benchmark/inventory.example.ini ansible/benchmark/playbook.yml
```


Remote mode from the UI prompts for SSH user/password, installs Docker if needed, copies `docker/benchmark`, brings containers up, and verifies suite SSH ports before Full AI starts.

Requires `ansible-core` (installed via `requirements.txt`).

RamiGPT integrates several tools for privilege escalation enumeration, including:

- **[BeRoot](https://github.com/AlessandroZ/BeRoot)**: A tool for identifying common privilege escalation vectors in Windows environments.
- **[LinPEAS](https://github.com/carlospolop/PEASS-ng/tree/master/linPEAS)**: A script that audits Linux environments for potential misconfigurations and vulnerabilities.

These tools are automatically employed or recommended by RamiGPT depending on the target environment.

## Project layout

Application code lives under `ramigpt/`. The repo root stays thin: `app.py` (entrypoint), `requirements.txt`, and `docker/`.

| Path | Role |
|------|------|
| `ramigpt/web/` | Flask/Socket.IO UI, templates, static assets |
| `ramigpt/ai/` | AI provider interface (OpenAI, Open WebUI) |
| `ramigpt/domain/` | Privilege-escalation prompt + root detection |
| `ramigpt/config/` | Settings loaded from `.env` secrets plus JSON user choices |
| `ramigpt/utils/` | Shared helpers and logging |
| `tools/` | Bundled priv-esc tooling (BeRoot, LinPEAS) |
| `scripts/` | Ops helpers (TLS cert generation) |
| `docs/` | Screenshots and documentation assets |
| `tests/` | Automated tests |
| `ramigpt/benchmark/` | Benchmark orchestrator (remote Ansible deploy + Full AI runs) |

| `docker/benchmark/` | One-image LPE labs (`MISCONFIG` profiles; ports 2170–2454). Integration guide: [`docker/benchmark/BENCHMARK_INTEGRATION.md`](docker/benchmark/BENCHMARK_INTEGRATION.md) |
| `ansible/benchmark/` | Ansible playbook to deploy targets on a remote host |
| `data/` | Runtime logs and sessions (gitignored) |
| `data/sessions/hosts/` | One JSON file per saved SSH session/host |
| `data/sessions/meta.json` | Groups + recent session ids |

| `certs/` | TLS certificates (gitignored) |

## Features

### AI provider settings

Switch between **Ollama**, **Open WebUI**, **OpenAI**, and **Cursor API** from
the **Settings** button. The selection persists in `data/ai_settings.json`;
`.env` remains the source for API keys and initial defaults.

### Import and export instructions

For example, to capture a flag:
>![alt text](docs/screenshots/poc_flag.gif)

### Use external tools for enumerations

For example, executing BeRoot and feeding the results to the AI:
>![alt text](docs/screenshots/proof_of_concept_beroot.gif)


## Disclaimer

RamiGPT is intended solely for **educational and authorized security testing**. Use it responsibly and only on systems where you have explicit permission to conduct tests.

