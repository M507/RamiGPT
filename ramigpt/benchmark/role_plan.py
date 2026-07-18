"""Benchmark batch role plan — repetitions per role/objective."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from ramigpt.config import Settings, get_settings, get_settings_manager
from ramigpt.config.settings import load_role_objectives

MAX_PLAN_ENTRIES = 10
MAX_REPS_PER_ENTRY = 50


@dataclass(frozen=True)
class RolePlanEntry:
    """One role slot (uses AI Settings role name when ``role`` omitted)."""

    repetitions: int = 1
    role: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _clamp_reps(value: Any) -> int:
    try:
        reps = int(value or 1)
    except (TypeError, ValueError):
        reps = 1
    return max(1, min(MAX_REPS_PER_ENTRY, reps))


def normalize_role_plan(
    role_plan: Optional[List[Any]] = None,
    *,
    repetitions: int = 1,
) -> List[RolePlanEntry]:
    """Build a validated role plan; every role uses the same run count."""
    shared_reps = _clamp_reps(repetitions)
    entries: List[RolePlanEntry] = []
    if isinstance(role_plan, list) and role_plan:
        roles_catalog = load_role_objectives()
        first = role_plan[0]
        if isinstance(first, dict) and first.get("repetitions") is not None:
            shared_reps = _clamp_reps(first.get("repetitions"))
        for raw in role_plan:
            if not isinstance(raw, dict):
                continue
            role = str(raw.get("role") or raw.get("role_objective") or "").strip() or None
            if role and role not in roles_catalog:
                raise ValueError(f"Unknown role/objective in role_plan: {role}")
            entries.append(RolePlanEntry(repetitions=shared_reps, role=role))
    if not entries:
        entries = [RolePlanEntry(repetitions=shared_reps)]

    if len(entries) > MAX_PLAN_ENTRIES:
        raise ValueError(f"role_plan supports at most {MAX_PLAN_ENTRIES} role entries")
    return entries


def apply_plan_entry_role(entry: RolePlanEntry) -> Settings:
    """Apply role plan entry to in-memory settings (never persists)."""
    cfg = get_settings()
    if not entry.role:
        return cfg
    roles = load_role_objectives()
    if entry.role not in roles:
        raise ValueError(f"Unknown role/objective: {entry.role}")
    return get_settings_manager().update(
        {"role_objective": entry.role, "rotate_role_objectives": 0},
        persist=False,
    )


def describe_role_plan(plan: List[RolePlanEntry]) -> Dict[str, Any]:
    fallback = get_settings().role_objective
    models = []
    for entry in plan:
        models.append(
            {
                "role": entry.role or fallback,
                "repetitions": entry.repetitions,
                "uses_ai_settings": not entry.role,
            }
        )
    return {
        "entries": models,
        "entry_count": len(plan),
        "repetitions_per_role": plan[0].repetitions if plan else 1,
        "total_runs": len(plan) * plan[0].repetitions if plan else 0,
    }
