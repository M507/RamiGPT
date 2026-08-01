# How to start benchmarking

End-to-end checklist: start RamiGPT with Docker, configure AI + remote lab, open the Benchmark UI, then start a run.

This guide shows the UI flow with screenshots. It does **not** start a benchmark for you — follow the commands and clicks when you are ready.

---

## Table of contents

1. [What you need](#1-what-you-need)
2. [Start the app with Docker](#2-start-the-app-with-docker)
3. [Configure the remote lab host](#3-configure-the-remote-lab-host)
4. [Optional CLI — deploy / verify targets](#4-optional-cli--deploy--verify-targets)
5. [Web UI — step by step](#5-web-ui--step-by-step)
6. [After the run](#6-after-the-run)
7. [Command cheat sheet](#7-command-cheat-sheet)

---

## 1. What you need

| Piece | Why |
|-------|-----|
| [Docker](https://docs.docker.com/get-docker/) + [Docker Compose](https://docs.docker.com/compose/install/) | Runs the RamiGPT web app |
| AI backend | Ollama, Open WebUI, OpenAI, or Cursor API |
| Remote Linux lab host | Ansible deploys the LPE Docker labs here (SSH as admin/`root`) |
| Network path | RamiGPT host → lab host (SSH), and RamiGPT → AI provider |

**Lab container SSH** (after deploy, per target port):

| Field | Value |
|-------|--------|
| Username | `lowpriv` |
| Password | `password` |
| Ports | `2170`–`2454` (selected targets only) |
| Root flag | `/root/flag.txt` → `FLAG{======RamiGPTi=====}` |

---

## 2. Start the app with Docker

### Step 2.1 — Clone and enter the repo

```sh
git clone https://github.com/M507/RamiGPT.git
cd RamiGPT
```

### Step 2.2 — Create `.env`

```sh
cp .env.example .env
```

Edit `.env` at least for:

```sh
# Pick one provider
AI_PROVIDER=openwebui          # or: ollama | openai | cursor

# Example: Open WebUI
OPENWEBUI_BASE_URL=http://10.10.10.82:8080
OPENWEBUI_API_KEY=your_openwebui_token
OPENWEBUI_MODEL=qwen3:14b

# Docker: disable auto-reload
APP_RELOAD=0

# Optional: GPU lab labels for collaborative merge keys
BENCHMARK_GPU_NAME=NVIDIA GeForce RTX 4070
BENCHMARK_GPU_VRAM=12282
BENCHMARK_GPU_DRIVER=591.86
BENCHMARK_CUDA_VERSION=13.1
```

### Step 2.3 — Bring the app up

```sh
docker compose -f docker/docker-compose.yml up -d
```

### Step 2.4 — Open the UI

```text
https://127.0.0.1:8443
```

Follow container logs if needed:

```sh
docker compose -f docker/docker-compose.yml logs -f flask-app
```

Stop later with:

```sh
docker compose -f docker/docker-compose.yml down
```

> **Local (non-Docker) alternative** — same UI afterward:
>
> ```sh
> python3 -m venv venv
> source venv/bin/activate
> chmod +x ./scripts/generate_certs.sh && ./scripts/generate_certs.sh
> pip install -r requirements.txt
> cp .env.example .env   # edit provider + keys
> python app.py
> ```

---

## 3. Configure the remote lab host

Copy the example and fill in the **lab machine** SSH (admin user used by Ansible — not `lowpriv`):

```sh
cp data/benchmark/remote.example.json data/benchmark/remote.json
```

Edit `data/benchmark/remote.json`:

```json
{
  "mode": "remote",
  "host": "10.10.1.109",
  "port": 22,
  "username": "root",
  "password": "CHANGE_ME",
  "timeout_seconds": 180,
  "tools": {
    "beroot": true
  }
}
```

`remote.json` is gitignored. The Benchmark modal prefills from this file when present.

---

## 4. Optional CLI — deploy / verify targets

You can let the UI deploy on **Start Benchmark**, or do it from the shell first.

### Deploy with Ansible

```sh
ansible-playbook -i ansible/benchmark/inventory.example.ini ansible/benchmark/playbook.yml
```

(The UI generates a temporary inventory from the Host / User / Password fields.)

### Verify misconfigs can actually get root

```sh
./scripts/benchmark/verify-misconfigs.sh <lab-host-ip>
# or
python3 -m ramigpt.benchmark.verify <lab-host-ip>
```

Subset:

```sh
./scripts/benchmark/verify-misconfigs.sh 10.10.1.109 sudo-vim cap-python
python3 -m ramigpt.benchmark.verify 10.10.1.109 --targets sudo-env,cap-python
```

Quick SSH smoke test into one lab container:

```sh
ssh -p 2211 lowpriv@<lab-host-ip>
# password: password
```

---

## 5. Web UI — step by step

Screenshots below are from a live session. Do **not** click **Start Benchmark** until you intend to run.

### Step 5.1 — Landing page

Open `https://127.0.0.1:8443`. From the welcome screen you can open **AI Settings**, **App Settings**, or **Benchmark**.

![Landing page — Welcome, Benchmark button in the top bar and main actions](screenshots/getting-started/guide_01_landing.png)

| Control | Action |
|---------|--------|
| **Benchmark** (top bar or main row) | Opens the Privilege Escalation Benchmark modal |
| **AI Settings** | Provider, model, API keys, max AI requests |
| **App Settings** | Role, parallel targets, history options |

---

### Step 5.2 — Configure AI

Click **AI Settings** → pick provider and model → **Test connection** → **Save**.

![AI Settings — provider, base URL, model, Test connection, Save](screenshots/getting-started/guide_02_ai_settings.png)

Typical checklist:

1. Set **Provider** (`Ollama` / `Open WebUI` / `OpenAI` / `Cursor API`).
2. Fill base URL + API key (keys stay in `.env`).
3. Choose **Model** (refresh icon pulls the live list).
4. Set **Max AI requests** for the Full AI loop.
5. Click **Test connection**, then **Save**.

---

### Step 5.3 — Open Benchmark → remote lab host

Click **Benchmark**. Section **1. Remote lab host** prefills from `data/benchmark/remote.json`.

![Benchmark modal — section 1 Remote lab host and start of Run options](screenshots/getting-started/guide_03_benchmark_remote.png)

| Field | Meaning |
|-------|---------|
| Host / IP | Lab machine where Docker targets are deployed |
| SSH port | Usually `22` |
| Username / Password | Ansible SSH (admin), **not** `lowpriv` |
| **Test SSH access** | Confirms RamiGPT can reach the lab host |

---

### Step 5.4 — Run options (model, role, tools)

Scroll to **2. Run options**.

![Run options — timeout, run plan, role plan, BeRoot / LinEnum / LinPEAS](screenshots/getting-started/guide_04_benchmark_run_options.png)

| Setting | Typical value |
|---------|----------------|
| Per-target timeout | `180` seconds |
| Run plan | Primary model from AI Settings; optional **+ Add model** |
| Role plan | e.g. Privilege Escalation Pentester |
| Tools | **BeRoot** on by default (runs before Full AI) |
| Target SSH note | `lowpriv` / `password` on selected ports |

Use **Configure AI** / **Configure roles** if you need to change provider or persona without leaving the modal.

---

### Step 5.5 — Pick targets

Section **3. Targets**. Default profile is **Regression sample (19)** — not all 285 labs.

![Targets — Select from profile dropdown and checked suite targets](screenshots/getting-started/guide_05_benchmark_targets.png)

**Select from** presets (examples):

| Group | Examples |
|-------|----------|
| Quick runs | Does it work? (3) · Regression sample (19) · Easy & portable (20) |
| Themed | Non-sudo · Detect-only · Cron & jobs · Credential leaks · SUID classics |
| Full families | Classic sudo · SUID · Writable · Capabilities · Credentials · … |
| Whole suite | **Select all (285)** |

Only **checked** targets are port-checked, deployed, verified, and scored.

Section **4. Sanity-check misconfigs** → **Test targets (get root)** runs the same probes as `verify-misconfigs.sh` (optional before a real run).

---

### Step 5.6 — Start (when you are ready)

Scroll to the footer. Status shows prior runs if any; **Idle** means nothing is running now.

![Run status footer — Auto-save collab results and Start Benchmark](screenshots/getting-started/guide_06_benchmark_start.png)

Before clicking **Start Benchmark**:

1. Confirm remote host + SSH work (**Test SSH access**).
2. Confirm AI **Test connection** succeeded.
3. Confirm target profile / checked list.
4. Optionally enable **Auto-save collab results** (writes under `data/benchmark/results/`).
5. Optionally enable **Rebuild remote labs** if a previous agent run may have corrupted a target (wipes bench containers/images on the remote host and recreates the official labs **before every run** in the batch).
6. Click **Start Benchmark**.

During a run: sessions appear under the **Benchmark** sidebar group; use **Stop** to abort.

---

## 6. After the run

| Artifact | Location |
|----------|----------|
| Per-run sheets | `data/benchmark/results/` |
| Collaborative master | `data/benchmark/results/master.json` |
| README / `benchmark.md` tables | Updated when master is rebuilt / collab save runs |
| Session logs | `data/logs/sessions/` |

Save later with **Save collab results** if you did not check auto-save. Commit result sheets only when you want to share stats with the team.

More detail: [`benchmark.md`](../benchmark.md), [`docker/benchmark/BENCHMARK_INTEGRATION.md`](../docker/benchmark/BENCHMARK_INTEGRATION.md).

---

## 7. Command cheat sheet

```sh
# --- App (Docker) ---
cp .env.example .env
docker compose -f docker/docker-compose.yml up -d
# open https://127.0.0.1:8443
docker compose -f docker/docker-compose.yml logs -f flask-app
docker compose -f docker/docker-compose.yml down

# --- Remote lab prefills ---
cp data/benchmark/remote.example.json data/benchmark/remote.json
# edit host / username / password

# --- Optional deploy + verify ---
ansible-playbook -i ansible/benchmark/inventory.example.ini ansible/benchmark/playbook.yml
./scripts/benchmark/verify-misconfigs.sh <lab-host-ip>
python3 -m ramigpt.benchmark.verify <lab-host-ip>

# --- Smoke-test one container ---
ssh -p 2211 lowpriv@<lab-host-ip>   # password: password
```

### UI path (short)

1. Open app → **AI Settings** → Test → Save  
2. **Benchmark** → fill remote lab → **Test SSH access**  
3. Set timeout / model / role / tools  
4. **Select from** a target profile (default: Regression sample)  
5. Optional: **Test targets (get root)**  
6. Optional: **Auto-save collab results**  
7. **Start Benchmark**
