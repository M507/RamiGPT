# Benchmark result examples (reference only)

These files show the **shape** of collaborative benchmark outputs. They are **not** live results and are **never** merged into `data/benchmark/results/master.json`.

| Path | Purpose |
|------|---------|
| [`run_sheet/result.json`](run_sheet/result.json) | One completed run sheet (schema v2) |
| [`run_sheet/summary.txt`](run_sheet/summary.txt) | Human-readable summary for the same run |
| [`../models/`](../models/) | Per-configuration model registry (`<key_name>.json` from Ollama `/api/show`) |
| [`master.sample.json`](master.sample.json) | Example master aggregate (uses `model_key_name`, not `provider/model`) |

Each run sheet includes **`model_key_name`** (model config), **`profile_label`** (model + hardware merge bucket), and **`hardware`** (from `.env` `BENCHMARK_GPU_*`).

## Live vs examples

| Location | Role |
|----------|------|
| `data/benchmark/results/` | **Live** collaborative store — empty until you run the suite |
| `data/benchmark/examples/` | **Reference** fixtures for contributors (this folder) |

After a real benchmark finishes, the app writes to `data/benchmark/results/`, rebuilds `master.json`, and updates the README stats section automatically.
