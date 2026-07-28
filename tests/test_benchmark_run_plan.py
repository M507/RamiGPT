"""Tests for benchmark multi-model run plans."""

from __future__ import annotations

import pytest

from ramigpt.benchmark.run_plan import (
    MAX_TOTAL_RUNS,
    RunPlanEntry,
    apply_plan_entry_model,
    flatten_run_plan,
    normalize_run_plan,
)
from ramigpt.config import get_settings


def test_normalize_legacy_repetitions():
    plan = normalize_run_plan(None, repetitions=3)
    assert plan == [RunPlanEntry(repetitions=3)]


def test_normalize_run_plan_entries():
    plan = normalize_run_plan(
        [
            {"repetitions": 2},
            {"provider": "openai", "model": "gpt-4o", "repetitions": 99},
        ]
    )
    assert len(plan) == 2
    assert plan[0].repetitions == 2
    assert plan[1].provider == "openai"
    assert plan[1].model == "gpt-4o"
    assert plan[1].repetitions == 2


def test_flatten_run_plan():
    plan = normalize_run_plan(
        [
            {"repetitions": 2},
            {"provider": "openai", "model": "gpt-4o"},
        ]
    )
    slots = flatten_run_plan(plan)
    assert len(slots) == 4
    assert slots[0][1] == 1
    assert slots[1][1] == 2
    assert slots[2][0].provider == "openai"
    assert slots[2][1] == 1
    assert slots[3][1] == 2


def test_total_runs_cap():
    with pytest.raises(ValueError, match=str(MAX_TOTAL_RUNS)):
        normalize_run_plan(
            [
                {"repetitions": 30},
                {"provider": "openai", "model": "gpt-4o", "repetitions": 25},
            ]
        )


def test_apply_plan_survives_get_settings_without_reload():
    """Run-plan model must stay in memory; reload() in the worker wiped it (bug fix)."""
    from ramigpt.config import get_settings_manager

    mgr = get_settings_manager()
    original = mgr.reload()
    try:
        mgr.update({"ai_provider": "ollama", "ollama_model": "qwen3:14b"}, persist=False)
        apply_plan_entry_model(
            RunPlanEntry(repetitions=1, provider="ollama", model="deepseek-r1:14b")
        )
        assert get_settings().ollama_model == "deepseek-r1:14b"
        # Old code called reload() here via _sync_run_ai_settings / _make_run.
        assert get_settings().ollama_model == "deepseek-r1:14b"
    finally:
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


def test_sync_run_ai_settings_uses_memory_not_disk():
    from ramigpt.benchmark.orchestrator import BenchmarkRun, _sync_run_ai_settings
    from ramigpt.config import get_settings_manager

    mgr = get_settings_manager()
    original = mgr.reload()
    try:
        mgr.update({"ai_provider": "ollama", "ollama_model": "qwen3:14b"}, persist=False)
        apply_plan_entry_model(
            RunPlanEntry(repetitions=1, provider="ollama", model="deepseek-r1:14b")
        )
        run = BenchmarkRun(id="test", mode="remote", timeout_seconds=60)
        run.provider = "ollama"
        run.model = "deepseek-r1:14b"
        cfg = _sync_run_ai_settings(run)
        assert cfg.ollama_model == "deepseek-r1:14b"
        assert run.model == "deepseek-r1:14b"
    finally:
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


def test_apply_plan_entry_model_switches_provider():
    from ramigpt.config import get_settings_manager

    mgr = get_settings_manager()
    original = mgr.reload()

    try:
        entry = RunPlanEntry(repetitions=1, provider="openai", model="gpt-test")
        cfg = apply_plan_entry_model(entry)
        assert cfg.ai_provider == "openai"
        assert cfg.openai_model == "gpt-test"
    finally:
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
