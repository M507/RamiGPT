"""Tests for combined model + role benchmark batch ordering."""

from __future__ import annotations

import pytest

from ramigpt.benchmark.batch_plan import flatten_batch_plan, normalize_batch_plans
from ramigpt.benchmark.run_plan import MAX_TOTAL_RUNS, RunPlanEntry, normalize_run_plan
from ramigpt.benchmark.role_plan import RolePlanEntry, normalize_role_plan


def test_flatten_batch_plan_model_major_role_minor():
    model_plan = normalize_run_plan(
        [
            {"repetitions": 2},
            {"provider": "openai", "model": "gpt-4o"},
        ]
    )
    role_plan = normalize_role_plan(
        [
            {"repetitions": 2},
            {"role": "Enumeration-First Pentester"},
        ]
    )
    slots = flatten_batch_plan(model_plan, role_plan)
    assert len(slots) == 16

    # Model entry 0, rep 1: both role entries (2 reps each)
    assert slots[0].model_entry_idx == 0 and slots[0].model_rep == 1
    assert slots[0].role_entry_idx == 0 and slots[0].role_rep == 1
    assert slots[3].model_entry_idx == 0 and slots[3].model_rep == 1
    assert slots[3].role_entry_idx == 1 and slots[3].role_rep == 2

    # Model entry 0, rep 2
    assert slots[4].model_entry_idx == 0 and slots[4].model_rep == 2
    assert slots[4].role_entry_idx == 0 and slots[4].role_rep == 1

    # Second model entry (last slot)
    assert slots[15].model_entry_idx == 1 and slots[15].model_rep == 2
    assert slots[15].model_entry.model == "gpt-4o"
    assert slots[15].role_entry.role == "Enumeration-First Pentester"
    assert slots[15].role_rep == 2


def test_normalize_batch_plans_legacy_repetitions():
    model_plan, role_plan, slots = normalize_batch_plans(
        repetitions=2,
        role_repetitions=3,
    )
    assert len(model_plan) == 1
    assert len(role_plan) == 1
    assert len(slots) == 6


def test_batch_total_runs_cap():
    model_plan = [RunPlanEntry(repetitions=7)]
    role_plan = [RolePlanEntry(repetitions=8)]
    with pytest.raises(ValueError, match=str(MAX_TOTAL_RUNS)):
        flatten_batch_plan(model_plan, role_plan)
