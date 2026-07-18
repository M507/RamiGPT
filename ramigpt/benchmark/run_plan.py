"""Benchmark batch run plan — repetitions per model."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

from ramigpt.config import Settings, get_settings, get_settings_manager

MAX_PLAN_ENTRIES = 10
MAX_TOTAL_RUNS = 50
MAX_REPS_PER_ENTRY = 50

MODEL_FIELD_BY_PROVIDER = {
    "ollama": "ollama_model",
    "openai": "openai_model",
    "openwebui": "openwebui_model",
    "cursor": "cursor_model",
}


@dataclass(frozen=True)
class RunPlanEntry:
    """One model slot in a benchmark batch (uses AI Settings when model/provider omitted)."""

    repetitions: int = 1
    provider: Optional[str] = None
    model: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def label(self, *, fallback_provider: str = "", fallback_model: str = "") -> str:
        provider = (self.provider or fallback_provider or "?").strip()
        model = (self.model or fallback_model or "?").strip()
        return f"{provider}/{model}"


def _clamp_reps(value: Any) -> int:
    try:
        reps = int(value or 1)
    except (TypeError, ValueError):
        reps = 1
    return max(1, min(MAX_REPS_PER_ENTRY, reps))


def normalize_run_plan(
    run_plan: Optional[List[Any]] = None,
    *,
    repetitions: int = 1,
) -> List[RunPlanEntry]:
    """
    Build a validated run plan.

    Legacy ``repetitions=N`` → one entry using current AI Settings.
    ``run_plan`` list → each item may set provider, model, repetitions.
    """
    entries: List[RunPlanEntry] = []
    if isinstance(run_plan, list) and run_plan:
        for raw in run_plan:
            if not isinstance(raw, dict):
                continue
            provider = str(raw.get("provider") or "").strip().lower() or None
            model = str(raw.get("model") or "").strip() or None
            if provider and provider not in MODEL_FIELD_BY_PROVIDER:
                raise ValueError(f"Unsupported provider in run_plan: {provider}")
            entries.append(
                RunPlanEntry(
                    repetitions=_clamp_reps(raw.get("repetitions")),
                    provider=provider,
                    model=model,
                )
            )
    if not entries:
        entries = [RunPlanEntry(repetitions=_clamp_reps(repetitions))]

    if len(entries) > MAX_PLAN_ENTRIES:
        raise ValueError(f"run_plan supports at most {MAX_PLAN_ENTRIES} model entries")

    total = sum(entry.repetitions for entry in entries)
    if total > MAX_TOTAL_RUNS:
        raise ValueError(f"Total benchmark runs cannot exceed {MAX_TOTAL_RUNS} (got {total})")
    if total < 1:
        raise ValueError("run_plan must schedule at least one run")
    return entries


def flatten_run_plan(plan: List[RunPlanEntry]) -> List[Tuple[RunPlanEntry, int, int]]:
    """Expand plan to (entry, repetition_within_entry, plan_entry_index)."""
    slots: List[Tuple[RunPlanEntry, int, int]] = []
    for entry_idx, entry in enumerate(plan):
        for within in range(1, entry.repetitions + 1):
            slots.append((entry, within, entry_idx))
    return slots


def apply_plan_entry_model(entry: RunPlanEntry) -> Settings:
    """Apply a run-plan entry to in-memory AI settings (never persists to disk)."""
    base = get_settings_manager().reload()
    if not entry.provider and not entry.model:
        return base

    updates: Dict[str, Any] = {}
    provider = (entry.provider or base.ai_provider or "ollama").strip().lower()
    if entry.provider:
        if provider not in MODEL_FIELD_BY_PROVIDER:
            raise ValueError(f"Unsupported AI provider: {provider}")
        updates["ai_provider"] = provider

    if entry.model:
        field = MODEL_FIELD_BY_PROVIDER.get(provider)
        if not field:
            raise ValueError(f"No model field for provider: {provider}")
        updates[field] = entry.model.strip()

    return get_settings_manager().update(updates, persist=False)


def describe_run_plan(plan: List[RunPlanEntry]) -> Dict[str, Any]:
    cfg = get_settings()
    fallback_provider = cfg.ai_provider
    fallback_model = cfg.active_model()
    models = []
    for entry in plan:
        models.append(
            {
                "provider": entry.provider or fallback_provider,
                "model": entry.model or fallback_model,
                "repetitions": entry.repetitions,
                "uses_ai_settings": not entry.provider and not entry.model,
            }
        )
    return {
        "entries": models,
        "entry_count": len(plan),
        "total_runs": sum(entry.repetitions for entry in plan),
    }
