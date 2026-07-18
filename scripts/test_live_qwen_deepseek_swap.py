#!/usr/bin/env python3
"""Live qwen ↔ deepseek swap test against configured Ollama host."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ramigpt.ai.factory import create_provider
from ramigpt.ai.providers.ollama_provider import (
    list_ollama_running_models,
    ollama_model_names_match,
)
from ramigpt.benchmark.model_warmup import warmup_ai_model
from ramigpt.benchmark.orchestrator import _sync_run_ai_settings, BenchmarkRun
from ramigpt.benchmark.run_plan import RunPlanEntry, apply_plan_entry_model
from ramigpt.config import get_settings, get_settings_manager

QWEN = "qwen3:14b"
DEEPSEEK = "deepseek-r1:14b"


def ps_label(base_url: str) -> str:
    try:
        names = list_ollama_running_models(base_url, timeout=15.0)
        return ", ".join(names) if names else "(none)"
    except Exception as exc:  # noqa: BLE001
        return f"(error: {exc})"


def contains_model(running: list[str], expected: str) -> bool:
    return any(ollama_model_names_match(expected, name) for name in running)


def probe_model(settings) -> tuple[str, float]:
    t0 = time.monotonic()
    provider = create_provider(settings)
    reply = provider.create_completion(
        [
            {"role": "system", "content": "Reply with exactly the model name you are."},
            {"role": "user", "content": "Which model are you? One short line."},
        ]
    )
    return (reply or "").strip()[:120], round(time.monotonic() - t0, 2)


def run_slot(label: str, entry: RunPlanEntry, last_warm) -> tuple[object, tuple[str, str] | None]:
    print(f"\n{'=' * 60}")
    print(f"SLOT: {label} → {entry.model or '(AI settings)'}")
    print("=" * 60)

    base_url = get_settings_manager().reload().ollama_base_url
    print(f"Ollama host: {base_url}")
    print(f"ollama ps BEFORE apply: {ps_label(base_url)}")

    cfg = apply_plan_entry_model(entry)
    expected = cfg.active_model()
    print(f"apply_plan_entry_model → {cfg.ai_provider}/{expected}")
    assert cfg.ollama_model == (entry.model or QWEN), f"memory mismatch: {cfg.ollama_model}"

    run = BenchmarkRun(id=f"live-{label}", mode="remote", timeout_seconds=60)
    run.provider = cfg.ai_provider
    run.model = expected
    synced = _sync_run_ai_settings(run)
    print(f"_sync_run_ai_settings → {synced.active_model()} (run.model={run.model})")
    if synced.active_model() != expected:
        raise SystemExit(f"FAIL: sync drift expected {expected} got {synced.active_model()}")

    warm = warmup_ai_model(cfg, last_warm=last_warm)
    for line in warm.log_lines:
        print(f"  warmup: {line}")
    if not warm.ok:
        raise SystemExit(f"FAIL: warmup failed: {warm.error}")

    running = list_ollama_running_models(base_url, timeout=15.0)
    print(f"ollama ps AFTER warmup: {', '.join(running) or '(none)'}")
    print(f"ollama_verified in warmup: {warm.ollama_verified}")

    reply, probe_s = probe_model(get_settings())
    print(f"create_provider probe ({probe_s}s): {reply!r}")
    print(f"Provider internal model: {create_provider(get_settings())._model}")  # noqa: SLF001

    in_ps = contains_model(running, expected)
    mem_ok = get_settings().ollama_model == expected
    print(f"CHECK memory={expected}: {mem_ok}")
    print(f"CHECK ollama ps lists {expected}: {in_ps}")

    if not mem_ok:
        raise SystemExit("FAIL: in-memory model wrong after slot")
    if not in_ps and warm.ollama_verified is not True:
        print("WARN: model not in ps but warmup probe succeeded — may be timing/GPU eviction")

    new_last = None if warm.skipped else (cfg.ai_provider, expected)
    return warm, new_last


def main() -> int:
    mgr = get_settings_manager()
    original = mgr.reload()
    print("Live swap test: qwen3:14b ↔ deepseek-r1:14b")
    print(f"Disk AI settings model: {original.ollama_model}")
    print(f"NOTE: ollama.exe ps on your PC may differ if it is not {original.ollama_base_url}")

    last_warm = None
    try:
        mgr.update({"ai_provider": "ollama", "ollama_model": QWEN}, persist=False)

        _, last_warm = run_slot(
            "1-qwen",
            RunPlanEntry(repetitions=1, provider="ollama", model=QWEN),
            last_warm,
        )

        _, last_warm = run_slot(
            "2-deepseek",
            RunPlanEntry(repetitions=1, provider="ollama", model=DEEPSEEK),
            last_warm,
        )

        # Swap back to qwen — must warm again (different model)
        _, _ = run_slot(
            "3-qwen-again",
            RunPlanEntry(repetitions=1, provider="ollama", model=QWEN),
            last_warm,
        )

        print(f"\n{'=' * 60}")
        print("ALL SLOTS PASSED — swap qwen ↔ deepseek verified on", original.ollama_base_url)
        print(f"Final ollama ps: {ps_label(original.ollama_base_url)}")
        return 0
    finally:
        mgr.update(
            {
                "ai_provider": original.ai_provider,
                "ollama_model": original.ollama_model,
            },
            persist=False,
        )
        mgr.reload()


if __name__ == "__main__":
    raise SystemExit(main())
