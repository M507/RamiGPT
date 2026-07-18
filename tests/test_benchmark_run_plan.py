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


def test_normalize_legacy_repetitions():
    plan = normalize_run_plan(None, repetitions=3)
    assert plan == [RunPlanEntry(repetitions=3)]


def test_normalize_run_plan_entries():
    plan = normalize_run_plan(
        [
            {"repetitions": 2},
            {"provider": "openai", "model": "gpt-4o", "repetitions": 1},
        ]
    )
    assert len(plan) == 2
    assert plan[0].repetitions == 2
    assert plan[1].provider == "openai"
    assert plan[1].model == "gpt-4o"


def test_flatten_run_plan():
    plan = normalize_run_plan(
        [
            {"repetitions": 2},
            {"provider": "openai", "model": "gpt-4o", "repetitions": 1},
        ]
    )
    slots = flatten_run_plan(plan)
    assert len(slots) == 3
    assert slots[0][1] == 1
    assert slots[1][1] == 2
    assert slots[2][0].provider == "openai"


def test_total_runs_cap():
    with pytest.raises(ValueError, match=str(MAX_TOTAL_RUNS)):
        normalize_run_plan(
            [
                {"repetitions": 30},
                {"provider": "openai", "model": "gpt-4o", "repetitions": 25},
            ]
        )


def test_apply_plan_entry_model_switches_provider(monkeypatch):
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
