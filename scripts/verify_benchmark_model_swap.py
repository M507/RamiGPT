"""
Verify benchmark model swap + warmup without running a full benchmark suite.

Usage:
  python scripts/verify_benchmark_model_swap.py          # in-memory checks only
  python scripts/verify_benchmark_model_swap.py --live   # also probe live Ollama (if configured)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as: python scripts/verify_benchmark_model_swap.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from typing import List, Tuple
from unittest.mock import MagicMock, patch

# Project root on path when invoked as script
from ramigpt.benchmark.model_warmup import warmup_ai_model
from ramigpt.benchmark.orchestrator import BenchmarkRun, _make_run, _sync_run_ai_settings
from ramigpt.benchmark.run_plan import (
    RunPlanEntry,
    apply_plan_entry_model,
    flatten_run_plan,
    normalize_run_plan,
)
from ramigpt.benchmark.targets import TARGETS
from ramigpt.config import get_settings, get_settings_manager


def _restore_settings(original) -> None:
    mgr = get_settings_manager()
    mgr.update(
        {
            "ai_provider": original.ai_provider,
            "ollama_model": original.ollama_model,
            "openai_model": original.openai_model,
            "openwebui_model": original.openwebui_model,
            "cursor_model": original.cursor_model,
        },
        persist=False,
    )
    mgr.reload()


def check_in_memory_swap() -> List[Tuple[str, bool, str]]:
    """Simulate the batch worker path: apply → make_run/sync → must keep run-plan model."""
    results: List[Tuple[str, bool, str]] = []
    mgr = get_settings_manager()
    original = mgr.reload()

    try:
        mgr.update(
            {"ai_provider": "ollama", "ollama_model": "qwen3:14b"},
            persist=False,
        )

        plan = normalize_run_plan(
            [
                {"repetitions": 1},
                {"provider": "ollama", "model": "deepseek-r1:14b", "repetitions": 1},
            ]
        )
        slots = flatten_run_plan(plan)
        last_warm = None
        warmed_models: List[str] = []

        disk_model = mgr.reload().ollama_model
        if disk_model != "qwen3:14b":
            results.append(
                (
                    "disk_baseline",
                    False,
                    f"disk settings should be qwen3:14b (got {disk_model})",
                )
            )
            return results

        for idx, (entry, _within, _entry_idx) in enumerate(slots, start=1):
            ai_cfg = apply_plan_entry_model(entry)
            expected = ai_cfg.active_model()

            run = BenchmarkRun(id=f"verify-{idx}", mode="remote", timeout_seconds=60)
            run.provider = ai_cfg.ai_provider
            run.model = expected

            synced = _sync_run_ai_settings(run)
            actual = synced.active_model()
            ok = actual == expected and run.model == expected
            results.append(
                (
                    f"run_{idx}_sync_preserves_{expected}",
                    ok,
                    f"expected {expected}, got memory={actual} run.model={run.model}",
                )
            )

            made = _make_run(
                mode="remote",
                timeout_seconds=60,
                tools_cfg={"beroot": True},
                merged_remote={"host": "127.0.0.1", "username": "u", "password": "p"},
                batch_id="verify-batch",
                repetition=idx,
                repetitions=len(slots),
                suite_targets=TARGETS[:1],
            )
            ok_make = made.model == get_settings().active_model() == expected
            results.append(
                (
                    f"run_{idx}_make_run_{expected}",
                    ok_make,
                    f"expected {expected}, got make_run.model={made.model}",
                )
            )

            with patch("ramigpt.benchmark.model_warmup.create_provider") as mock_cp:
                with patch(
                    "ramigpt.benchmark.model_warmup.list_ollama_running_models"
                ) as mock_ps:
                    mock_ps.side_effect = [["qwen3:14b"], [expected]]
                    prov = MagicMock()
                    prov.create_completion.return_value = "ok"
                    mock_cp.return_value = prov
                    warm = warmup_ai_model(ai_cfg, last_warm=last_warm)
            results.append(
                (
                    f"run_{idx}_warmup",
                    warm.ok,
                    warm.log_lines[-1] if warm.log_lines else warm.error or "",
                )
            )
            if warm.ok and not warm.skipped:
                last_warm = (ai_cfg.ai_provider, ai_cfg.active_model())
                warmed_models.append(expected)

        # Run 2 should trigger warmup; run 1 same model as disk if primary uses AI settings
        results.append(
            (
                "warmup_count",
                len(warmed_models) >= 2 or warmed_models[-1:] == ["deepseek-r1:14b"],
                f"warmed={warmed_models}",
            )
        )

        # Regression: reload after apply would undo swap (documents old bug)
        apply_plan_entry_model(
            RunPlanEntry(repetitions=1, provider="ollama", model="deepseek-r1:14b")
        )
        mgr.reload()
        reloaded_model = get_settings().ollama_model
        results.append(
            (
                "regression_reload_wipes_swap",
                reloaded_model == "qwen3:14b",
                f"reload() must revert to disk (got {reloaded_model}) — proves why reload-in-worker was wrong",
            )
        )
    finally:
        _restore_settings(original)

    return results


def check_live_ollama() -> List[Tuple[str, bool, str]]:
    results: List[Tuple[str, bool, str]] = []
    cfg = get_settings()
    if cfg.ai_provider != "ollama" or not cfg.ollama_base_url:
        results.append(
            ("live_ollama", False, "skipped — AI provider is not ollama or base URL missing")
        )
        return results

    from ramigpt.ai.providers.ollama_provider import list_ollama_running_models

    primary = cfg.ollama_model
    try:
        tags = __import__(
            "ramigpt.ai.model_catalog", fromlist=["list_models_for_provider"]
        ).list_models_for_provider("ollama")
    except Exception as exc:  # noqa: BLE001
        results.append(("live_list_models", False, str(exc)))
        return results

    alt = next((m for m in tags if m != primary), None)
    if not alt:
        results.append(
            (
                "live_ollama",
                False,
                f"skipped — only one Ollama model installed ({primary})",
            )
        )
        return results

    mgr = get_settings_manager()
    original = mgr.reload()
    try:
        ps0 = list_ollama_running_models(cfg.ollama_base_url, timeout=12.0)

        apply_plan_entry_model(
            RunPlanEntry(repetitions=1, provider="ollama", model=alt)
        )
        assert get_settings().ollama_model == alt

        warm = warmup_ai_model(get_settings(), last_warm=None)
        ps1 = list_ollama_running_models(cfg.ollama_base_url, timeout=12.0)

        results.append(("live_warmup_ok", warm.ok, warm.log_lines[-1] if warm.log_lines else warm.error or ""))
        results.append(
            (
                "live_ps_changed_or_lists_alt",
                warm.ollama_verified is True or alt in ps1 or any(alt.split(":")[0] in p for p in ps1),
                f"before={ps0} after={ps1} expected~={alt}",
            )
        )
        results.append(
            (
                "live_memory_still_alt_after_warmup",
                get_settings().ollama_model == alt,
                f"memory model={get_settings().ollama_model}",
            )
        )
    finally:
        _restore_settings(original)

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify benchmark model swap logic")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run live Ollama warmup probe (requires reachable Ollama with 2+ models)",
    )
    args = parser.parse_args()

    all_results = check_in_memory_swap()
    if args.live:
        all_results.extend(check_live_ollama())

    failed = 0
    print("Benchmark model swap verification")
    print("=" * 60)
    for name, ok, detail in all_results:
        status = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"[{status}] {name}")
        print(f"       {detail}")

    print("=" * 60)
    if failed:
        print(f"{failed} check(s) failed")
        return 1
    print(f"All {len(all_results)} check(s) passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
