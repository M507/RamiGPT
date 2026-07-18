# Benchmark model registry

Each **unique model configuration** gets its own JSON file here when a benchmark run starts.

## Model `key_name` (weights + inference config)

The registry `key_name` identifies the **model only** — not the GPU. It is derived from:

- **Ollama:** `POST /api/show` details (family, parameter size, quantization, modelfile `PARAMETER` lines) plus `/api/tags` digest
- **Other providers:** provider + model tag + base URL fingerprint

Example model key:

```text
ollama-qwen3-14b-qwen3-14.8B-q4_k_m-abc123456789
```

## Collaborative profile (model + hardware)

Runs merge in the master when **profile + scenario** match.

| Layer | Identifies | Example |
|-------|-----------|---------|
| **Model `key_name`** | Weights + modelfile params | `ollama-qwen3-14b-…` |
| **Hardware lab** | `BENCHMARK_GPU_*` in `.env` | RTX 4070 · 12282 MiB |
| **Profile label** | Model + hardware (display + merge bucket) | `ollama-qwen3-14b-… · NVIDIA GeForce RTX 4070 · 12282 MiB` |
| **Scenario** | Role + target + tools | Enumeration-First · sudo-vim · beroot |

Same model on two different GPUs → **one registry file**, **two profile rows** in the master.

## Files

| Path | Purpose |
|------|---------|
| `<key_name>.json` | Canonical record for one model configuration |
| [`../examples/`](../examples/) | Sample result/master shapes (not live data) |

## Hardware profile

GPU details are **not** part of the model `key_name`. They come from `.env` (`BENCHMARK_GPU_*`), are copied into each run's `result.json`, and combine with `key_name` into the collaborative **profile**.

Use the same merge-key fields across contributors when you want runs on the same lab GPU to merge: GPU name, VRAM MiB, driver, and CUDA. `BENCHMARK_GPU_VRAM` is VRAM in **MiB** (integer). `BENCHMARK_GPU_POWER_LIMIT` is watts (integer, no unit suffix) — stored on each run for lab context but **not** part of merge keys.

See [`.env.example`](../../../.env.example) for the expected variables.
