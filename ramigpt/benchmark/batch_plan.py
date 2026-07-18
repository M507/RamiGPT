"""Combine model + role plans into ordered benchmark batch slots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from ramigpt.benchmark.role_plan import RolePlanEntry, describe_role_plan, normalize_role_plan
from ramigpt.benchmark.run_plan import (
    MAX_TOTAL_RUNS,
    RunPlanEntry,
    describe_run_plan,
    normalize_run_plan,
)
from ramigpt.config import get_settings


@dataclass(frozen=True)
class BatchSlot:
    """One full-suite benchmark run: model + role + repetition indices."""

    model_entry: RunPlanEntry
    role_entry: RolePlanEntry
    model_rep: int
    role_rep: int
    model_entry_idx: int
    role_entry_idx: int


def flatten_batch_plan(
    model_plan: List[RunPlanEntry],
    role_plan: List[RolePlanEntry],
) -> List[BatchSlot]:
    """
    Expand plans in model-major, role-minor order:

    for each model entry (× model repetitions):
      for each role entry (× role repetitions):
        one full benchmark suite run
    """
    slots: List[BatchSlot] = []
    for model_idx, model_entry in enumerate(model_plan):
        for model_rep in range(1, model_entry.repetitions + 1):
            for role_idx, role_entry in enumerate(role_plan):
                for role_rep in range(1, role_entry.repetitions + 1):
                    slots.append(
                        BatchSlot(
                            model_entry=model_entry,
                            role_entry=role_entry,
                            model_rep=model_rep,
                            role_rep=role_rep,
                            model_entry_idx=model_idx,
                            role_entry_idx=role_idx,
                        )
                    )
    if len(slots) > MAX_TOTAL_RUNS:
        raise ValueError(
            f"Total benchmark runs cannot exceed {MAX_TOTAL_RUNS} (got {len(slots)})"
        )
    if not slots:
        raise ValueError("batch plan must schedule at least one run")
    return slots


def normalize_batch_plans(
    *,
    run_plan: List[Any] | None = None,
    role_plan: List[Any] | None = None,
    repetitions: int = 1,
    role_repetitions: int = 1,
) -> Tuple[List[RunPlanEntry], List[RolePlanEntry], List[BatchSlot]]:
    model_plan = normalize_run_plan(run_plan, repetitions=repetitions)
    roles = normalize_role_plan(role_plan, repetitions=role_repetitions)
    slots = flatten_batch_plan(model_plan, roles)
    return model_plan, roles, slots


def describe_batch_plan(
    model_plan: List[RunPlanEntry],
    role_plan: List[RolePlanEntry],
) -> Dict[str, Any]:
    cfg = get_settings()
    return {
        "model_plan": describe_run_plan(model_plan),
        "role_plan": describe_role_plan(role_plan),
        "total_runs": (
            len(model_plan)
            * (model_plan[0].repetitions if model_plan else 1)
            * len(role_plan)
            * (role_plan[0].repetitions if role_plan else 1)
        ),
        "model_entry_count": len(model_plan),
        "role_entry_count": len(role_plan),
        "fallback_provider": cfg.ai_provider,
        "fallback_model": cfg.active_model(),
        "fallback_role": cfg.role_objective,
    }
