"""Tests for benchmark multi-role plans."""

from __future__ import annotations

import pytest

from ramigpt.benchmark.role_plan import (
    RolePlanEntry,
    apply_plan_entry_role,
    normalize_role_plan,
)
from ramigpt.config import get_settings, get_settings_manager


def test_normalize_legacy_role_repetitions():
    plan = normalize_role_plan(None, repetitions=3)
    assert plan == [RolePlanEntry(repetitions=3)]


def test_normalize_role_plan_entries():
    plan = normalize_role_plan(
        [
            {"repetitions": 2},
            {"role": "Enumeration-First Pentester", "repetitions": 99},
        ]
    )
    assert len(plan) == 2
    assert plan[0].repetitions == 2
    assert plan[0].role is None
    assert plan[1].role == "Enumeration-First Pentester"
    assert plan[1].repetitions == 2


def test_unknown_role_rejected():
    with pytest.raises(ValueError, match="Unknown role/objective"):
        normalize_role_plan([{"role": "Not A Real Role", "repetitions": 1}])


def test_apply_plan_entry_role():
    mgr = get_settings_manager()
    original = mgr.reload()
    try:
        apply_plan_entry_role(
            RolePlanEntry(repetitions=1, role="Enumeration-First Pentester")
        )
        assert get_settings().role_objective == "Enumeration-First Pentester"
        assert get_settings().rotate_role_objectives == 0
    finally:
        mgr.update(
            {
                "role_objective": original.role_objective,
                "rotate_role_objectives": original.rotate_role_objectives,
            },
            persist=False,
        )
        mgr.reload()


def test_apply_plan_entry_role_survives_without_reload():
    mgr = get_settings_manager()
    original = mgr.reload()
    try:
        apply_plan_entry_role(
            RolePlanEntry(repetitions=1, role="Minimal-Noise Operator")
        )
        assert get_settings().role_objective == "Minimal-Noise Operator"
        assert get_settings().role_objective == "Minimal-Noise Operator"
    finally:
        mgr.update(
            {
                "role_objective": original.role_objective,
                "rotate_role_objectives": original.rotate_role_objectives,
            },
            persist=False,
        )
        mgr.reload()
