"""Ensure the configured AI model is loaded before benchmark targets run."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ramigpt.ai.factory import create_provider
from ramigpt.ai.probe import PROVIDER_PROBE_MESSAGES
from ramigpt.ai.providers.ollama_provider import (
    list_ollama_running_models,
    ollama_model_names_match,
)
from ramigpt.config import Settings

@dataclass
class ModelWarmupResult:
    ok: bool
    skipped: bool = False
    provider: str = ""
    model: str = ""
    probe_seconds: Optional[float] = None
    ollama_ps_before: List[str] = field(default_factory=list)
    ollama_ps_after: List[str] = field(default_factory=list)
    ollama_verified: Optional[bool] = None
    reply_preview: str = ""
    error: Optional[str] = None
    log_lines: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _fmt_ps(names: List[str]) -> str:
    if not names:
        return "(none)"
    return ", ".join(names)


def _ollama_ps_snapshot(settings: Settings) -> List[str]:
    if not settings.ollama_base_url:
        return []
    try:
        return list_ollama_running_models(settings.ollama_base_url, timeout=12.0)
    except Exception:  # noqa: BLE001
        return []


def _ollama_ps_contains_model(running: List[str], expected: str) -> bool:
    return any(ollama_model_names_match(expected, name) for name in running)


def warmup_ai_model(
    settings: Settings,
    *,
    last_warm: Optional[Tuple[str, str]] = None,
) -> ModelWarmupResult:
    """
    Load/verify the active model before benchmark work.

    Skips when ``last_warm`` matches the current provider/model (same batch slot).
    For Ollama, snapshots ``/api/ps`` before/after a tiny completion probe.
    """
    provider = (settings.ai_provider or "").strip().lower()
    model = (settings.active_model() or "").strip()
    key = (provider, model)

    if last_warm and last_warm == key:
        line = f"AI model warmup skipped — {provider}/{model} already verified this batch"
        return ModelWarmupResult(
            ok=True,
            skipped=True,
            provider=provider,
            model=model,
            log_lines=[line],
        )

    result = ModelWarmupResult(ok=False, provider=provider, model=model)
    lines: List[str] = [
        f"AI model warmup starting — {provider}/{model} (probe before benchmark targets)",
    ]

    ps_before: List[str] = []
    ps_after: List[str] = []
    if provider == "ollama":
        ps_before = _ollama_ps_snapshot(settings)
        lines.append(f"Ollama ps before warmup: {_fmt_ps(ps_before)}")

    started = time.monotonic()
    try:
        ai = create_provider(settings)
        reply = ai.create_completion(list(PROVIDER_PROBE_MESSAGES))
        probe_seconds = round(time.monotonic() - started, 3)
        preview = (reply or "").strip().replace("\n", " ")
        if len(preview) > 80:
            preview = preview[:77] + "..."

        result.probe_seconds = probe_seconds
        result.reply_preview = preview

        if provider == "ollama":
            ps_after = _ollama_ps_snapshot(settings)
            result.ollama_ps_before = ps_before
            result.ollama_ps_after = ps_after
            verified = _ollama_ps_contains_model(ps_after, model)
            result.ollama_verified = verified
            lines.append(f"Ollama ps after warmup: {_fmt_ps(ps_after)}")
            if verified:
                lines.append(
                    f"AI model warmup OK in {probe_seconds}s — "
                    f"{provider}/{model} loaded (probe reply: {preview or '—'})"
                )
            else:
                lines.append(
                    f"AI model warmup probe OK in {probe_seconds}s — "
                    f"{provider}/{model} (probe reply: {preview or '—'}) "
                    f"but model not listed in ollama ps yet"
                )
        else:
            lines.append(
                f"AI model warmup OK in {probe_seconds}s — "
                f"{provider}/{model} (probe reply: {preview or '—'})"
            )

        result.ok = True
        result.log_lines = lines
        return result
    except Exception as exc:  # noqa: BLE001
        probe_seconds = round(time.monotonic() - started, 3)
        result.probe_seconds = probe_seconds
        result.error = str(exc)
        if provider == "ollama":
            result.ollama_ps_before = ps_before
            result.ollama_ps_after = _ollama_ps_snapshot(settings)
        lines.append(
            f"AI model warmup FAILED for {provider}/{model} after {probe_seconds}s: {exc}"
        )
        result.log_lines = lines
        return result
