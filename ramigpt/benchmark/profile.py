"""Collaborative benchmark profile identity — model config + hardware lab profile."""

from __future__ import annotations

from typing import Any, Dict

from ramigpt.benchmark.hardware import hardware_key, hardware_label


def aggregate_model_key(model_key_name: str, provider: str, model: str) -> str:
    key = (model_key_name or "").strip()
    if key:
        return key
    provider = (provider or "").strip()
    model = (model or "").strip()
    if provider and model:
        return f"{provider}/{model}"
    return model or provider or "unknown"


def collaborative_profile_key(
    model_key_name: str,
    provider: str,
    model: str,
    hardware: Dict[str, Any],
) -> str:
    """Merge bucket id: same model ``key_name`` + same hardware lab profile → merge."""
    return f"{aggregate_model_key(model_key_name, provider, model)}|{hardware_key(hardware)}"


def parse_profile_key(profile_key: str) -> Dict[str, str]:
    model_part, _, hw_part = profile_key.partition("|")
    return {
        "model_key_name": model_part or "unknown",
        "hardware_key": hw_part or "unknown",
    }


def profile_display_label(
    model_key_name: str,
    hardware: Dict[str, Any],
    *,
    provider: str = "",
    model: str = "",
) -> str:
    """
    Human-readable collaborative profile label.

    Example: ``ollama-qwen3-14b-... · NVIDIA GeForce RTX 4070 · 12282 MiB · CUDA 13.1``
    """
    model_part = aggregate_model_key(model_key_name, provider, model)
    hw = hardware_label(hardware)
    if not hw or hw == "unknown":
        return model_part
    return f"{model_part} · {hw}"
