"""Integration tests for benchmark model swap (no full benchmark run)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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


def _restore(original) -> None:
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


def test_batch_swap_sequence_preserves_second_model():
    """Reproduce batch 9b560e08 bug: run 2 planned deepseek must survive sync/make_run."""
    mgr = get_settings_manager()
    original = mgr.reload()
    try:
        mgr.update({"ai_provider": "ollama", "ollama_model": "qwen3:14b"}, persist=False)

        plan = normalize_run_plan(
            [
                {"repetitions": 1},
                {"provider": "ollama", "model": "deepseek-r1:14b", "repetitions": 1},
            ]
        )
        slots = flatten_run_plan(plan)

        # Run 1 — primary (disk model)
        cfg1 = apply_plan_entry_model(slots[0][0])
        assert cfg1.active_model() == "qwen3:14b"
        run1 = BenchmarkRun(id="r1", mode="remote", timeout_seconds=60)
        run1.provider, run1.model = cfg1.ai_provider, cfg1.active_model()
        synced1 = _sync_run_ai_settings(run1)
        assert synced1.active_model() == "qwen3:14b"

        # Run 2 — swapped model (was broken before fix)
        cfg2 = apply_plan_entry_model(slots[1][0])
        assert cfg2.active_model() == "deepseek-r1:14b"

        run2 = _make_run(
            mode="remote",
            timeout_seconds=60,
            tools_cfg={"beroot": True},
            merged_remote={"host": "h", "username": "u", "password": "p"},
            batch_id="batch-test",
            repetition=2,
            repetitions=2,
            suite_targets=TARGETS[:1],
        )
        assert run2.model == "deepseek-r1:14b"
        assert get_settings().ollama_model == "deepseek-r1:14b"

        synced2 = _sync_run_ai_settings(run2)
        assert synced2.active_model() == "deepseek-r1:14b"
        assert run2.model == "deepseek-r1:14b"
    finally:
        _restore(original)


def test_reload_after_apply_reverts_swap_documents_old_bug():
    mgr = get_settings_manager()
    original = mgr.reload()
    try:
        mgr.update({"ai_provider": "ollama", "ollama_model": "qwen3:14b"}, persist=False)
        apply_plan_entry_model(
            RunPlanEntry(repetitions=1, provider="ollama", model="deepseek-r1:14b")
        )
        assert get_settings().ollama_model == "deepseek-r1:14b"
        mgr.reload()
        assert get_settings().ollama_model == "qwen3:14b"
    finally:
        _restore(original)


def test_warmup_runs_on_swap_skips_on_repeat():
    mgr = get_settings_manager()
    original = mgr.reload()
    try:
        settings = mgr.update(
            {"ai_provider": "ollama", "ollama_model": "deepseek-r1:14b"},
            persist=False,
        )
        with patch("ramigpt.benchmark.model_warmup.create_provider") as mock_cp:
            with patch("ramigpt.benchmark.model_warmup.list_ollama_running_models") as mock_ps:
                mock_ps.return_value = ["deepseek-r1:14b"]
                prov = MagicMock()
                prov.create_completion.return_value = "ok"
                mock_cp.return_value = prov

                first = warmup_ai_model(settings, last_warm=None)
                second = warmup_ai_model(settings, last_warm=("ollama", "deepseek-r1:14b"))

        assert first.ok and not first.skipped
        assert second.ok and second.skipped
        assert mock_cp.call_count == 1
    finally:
        _restore(original)
