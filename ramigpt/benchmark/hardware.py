"""Benchmark host hardware profile supplied via environment variables."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from ramigpt.paths import ENV_PATH

_REMOTE_AI_PROVIDERS = frozenset({"openwebui"})

_HARDWARE_ENV_KEYS = {
    "gpu_name": "BENCHMARK_GPU_NAME",
    "gpu_vram": "BENCHMARK_GPU_VRAM",
    "gpu_power_limit": "BENCHMARK_GPU_POWER_LIMIT",
    "gpu_driver": "BENCHMARK_GPU_DRIVER",
    "cuda_version": "BENCHMARK_CUDA_VERSION",
}

# Fields that define collaborative merge keys (profile / scenario grouping).
HARDWARE_MERGE_KEY_FIELDS = (
    "gpu_name",
    "gpu_vram",
    "gpu_driver",
    "cuda_version",
)

# Slug order for ``hardware_key()`` (must stay stable once runs exist in git).
HARDWARE_MERGE_KEY_SLUG_ORDER = (
    "gpu_name",
    "gpu_vram",
    "cuda_version",
    "gpu_driver",
)

# Stored on each run sheet for lab context; does not affect merge keys.
HARDWARE_METADATA_FIELDS = (
    "gpu_power_limit",
)

HARDWARE_STORED_FIELDS = HARDWARE_MERGE_KEY_FIELDS + HARDWARE_METADATA_FIELDS


def _parse_mib(value: Any) -> Optional[int]:
    """Parse VRAM as an integer number of MiB."""
    text = str(value or "").strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    match = re.search(r"(\d+)\s*MiB", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"\d+", text)
    if match:
        return int(match.group(0))
    return None


def _parse_watts(value: Any) -> Optional[int]:
    """Parse power limit as an integer number of watts (no unit suffix)."""
    text = re.sub(r"(?i)\s*w\s*$", "", str(value or "").strip())
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _normalize_hardware_field(field: str, value: str) -> Any:
    if field == "gpu_vram":
        parsed = _parse_mib(value)
        return parsed if parsed is not None else value
    if field == "gpu_power_limit":
        parsed = _parse_watts(value)
        return parsed if parsed is not None else value
    return value


def load_benchmark_hardware(*, reload_env: bool = False) -> Dict[str, Any]:
    """
    Load the lab GPU profile for benchmark runs.

    Values come from ``.env`` (see ``.env.example``). Empty strings are omitted.
    ``gpu_vram`` is stored as MiB (int); ``gpu_power_limit`` as watts (int).
    """
    if reload_env:
        load_dotenv(ENV_PATH, override=False)
    profile: Dict[str, Any] = {}
    for field, env_key in _HARDWARE_ENV_KEYS.items():
        value = (os.getenv(env_key) or "").strip()
        if value:
            profile[field] = _normalize_hardware_field(field, value)
    return profile


# Stable collaborative profile for remote/proxy AI providers (not local GPU lab).
OPENWEBUI_HARDWARE_PROFILE: Dict[str, str] = {
    "gpu_name": "Online AI Service",
    "gpu_driver": "Open WebUI proxy",
}


def openwebui_hardware_profile() -> Dict[str, Any]:
    """
    Synthetic lab profile for Open WebUI runs.

    Open WebUI fronts opaque backend hardware, so benchmark results should not
    inherit the local Ollama GPU profile from ``.env``. The profile is fixed
    (no host/IP) so contributors merge on model + provider, not private URLs.
    """
    return dict(OPENWEBUI_HARDWARE_PROFILE)


def resolve_benchmark_hardware(
    *,
    provider: str = "",
    reload_env: bool = False,
) -> Dict[str, Any]:
    """
    Return the hardware profile stored on benchmark run sheets.

    Local providers (e.g. Ollama) use ``BENCHMARK_GPU_*`` from ``.env``.
    Remote proxy providers substitute a stable online-service profile instead.
    """
    name = (provider or "").strip().lower()
    if name in _REMOTE_AI_PROVIDERS:
        if name == "openwebui":
            return openwebui_hardware_profile()
    return load_benchmark_hardware(reload_env=reload_env)


def hardware_is_configured(profile: Dict[str, Any]) -> bool:
    return bool(profile)


def _slug_part(value: str, *, max_len: int = 32) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", (value or "").strip().lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return (cleaned[:max_len].strip("-") or "")


def _format_vram_label(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, int):
        return f"{value} MiB"
    text = str(value).strip()
    if text.isdigit():
        return f"{text} MiB"
    return text


def _hardware_field_value(field: str, raw: Any) -> Optional[str]:
    if raw is None or raw == "":
        return None
    if field == "gpu_vram":
        mib = _parse_mib(raw)
        return str(mib if mib is not None else raw)
    if field == "gpu_power_limit":
        watts = _parse_watts(raw)
        return str(watts if watts is not None else raw)
    return str(raw).strip()


def hardware_identity(profile: Dict[str, Any]) -> Dict[str, str]:
    """Return merge-key fields only (name, VRAM MiB, driver, CUDA)."""
    out: Dict[str, str] = {}
    for field in HARDWARE_MERGE_KEY_FIELDS:
        value = _hardware_field_value(field, (profile or {}).get(field))
        if value:
            out[field] = value
    return out


def hardware_metadata(profile: Dict[str, Any]) -> Dict[str, str]:
    """Return lab metadata stored on run sheets but excluded from merge keys."""
    out: Dict[str, str] = {}
    for field in HARDWARE_METADATA_FIELDS:
        value = _hardware_field_value(field, (profile or {}).get(field))
        if value:
            out[field] = value
    return out


def hardware_key(profile: Dict[str, Any]) -> str:
    """
    Stable slug for collaborative merging.

    Uses ``HARDWARE_MERGE_KEY_FIELDS`` only. ``gpu_power_limit`` is stored on run
    sheets but does not affect this key.
    """
    identity = hardware_identity(profile)
    if not identity:
        return "unknown"
    slug_limits = {
        "gpu_name": 32,
        "gpu_vram": 24,
        "cuda_version": 12,
        "gpu_driver": 12,
    }
    parts = [
        _slug_part(identity[field], max_len=slug_limits[field])
        for field in HARDWARE_MERGE_KEY_SLUG_ORDER
        if identity.get(field) and _slug_part(identity[field], max_len=slug_limits[field])
    ]
    return "-".join(parts) if parts else "unknown"


def hardware_label(profile: Dict[str, Any]) -> str:
    """Human-readable hardware label for README tables."""
    identity = hardware_identity(profile)
    if not identity:
        return "unknown"
    name = identity.get("gpu_name") or "unknown GPU"
    bits = [name]
    vram_label = _format_vram_label(identity.get("gpu_vram"))
    if vram_label:
        bits.append(vram_label)
    if identity.get("cuda_version"):
        bits.append(f"CUDA {identity['cuda_version']}")
    return " · ".join(bits)
