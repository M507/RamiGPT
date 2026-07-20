"""Benchmark model registry — unique key_name per provider/model configuration."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ramigpt.benchmark.hardware import REMOTE_AI_PROVIDERS
from ramigpt.ai.providers.ollama_provider import (
    fetch_ollama_show,
    fetch_ollama_tag_info,
)
from ramigpt.config import Settings
from ramigpt.paths import BENCHMARK_MODELS_DIR, PROJECT_ROOT, ensure_runtime_dirs
from ramigpt.utils import debug_logger

MODEL_REGISTRY_SCHEMA_VERSION = 1
_LOG_PREFIX = "[benchmark-model-registry]"


def _log_info(message: str) -> None:
    debug_logger.info(f"{_LOG_PREFIX} {message}")


def _log_warning(message: str) -> None:
    debug_logger.warning(f"{_LOG_PREFIX} {message}")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug_part(value: str, *, max_len: int = 40) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", (value or "").strip().lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return (cleaned[:max_len].strip("-") or "unknown")


def _relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def parse_modelfile_parameters(modelfile: str) -> Dict[str, str]:
    """Extract ``PARAMETER name value`` lines from an Ollama modelfile."""
    params: Dict[str, str] = {}
    for line in (modelfile or "").splitlines():
        stripped = line.strip()
        if not stripped.upper().startswith("PARAMETER "):
            continue
        body = stripped[len("PARAMETER ") :].strip()
        if not body:
            continue
        name, _, value = body.partition(" ")
        key = name.strip()
        if key:
            params[key] = value.strip()
    return params


def _short_hash(payload: Dict[str, Any], *, length: int = 8) -> str:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def build_ollama_fingerprint(
    *,
    model: str,
    show: Dict[str, Any],
    tag_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    details = show.get("details") if isinstance(show.get("details"), dict) else {}
    tag_info = tag_info or {}
    parameters = parse_modelfile_parameters(str(show.get("modelfile") or ""))
    digest = (tag_info.get("digest") or show.get("digest") or "").strip()
    return {
        "provider": "ollama",
        "model": model,
        "family": details.get("family"),
        "families": details.get("families"),
        "parameter_size": details.get("parameter_size"),
        "quantization_level": details.get("quantization_level"),
        "format": details.get("format"),
        "parent_model": details.get("parent_model"),
        "digest": digest,
        "size_bytes": tag_info.get("size"),
        "modified_at": tag_info.get("modified_at"),
        "parameters": parameters,
        "capabilities": show.get("capabilities"),
    }


def build_provider_fingerprint(settings: Settings) -> Dict[str, Any]:
    provider = (settings.ai_provider or "").strip().lower()
    model = (settings.active_model() or "").strip()
    if provider == "ollama":
        if not settings.ollama_base_url:
            raise RuntimeError("OLLAMA_BASE_URL is not configured")
        show = fetch_ollama_show(settings.ollama_base_url, model)
        try:
            tag_info = fetch_ollama_tag_info(settings.ollama_base_url, model)
        except Exception as exc:  # noqa: BLE001
            _log_warning(f"tag info unavailable for {model}: {exc}")
            tag_info = {}
        return build_ollama_fingerprint(model=model, show=show, tag_info=tag_info)

    fp: Dict[str, Any] = {
        "provider": provider,
        "model": model,
    }
    if provider == "openai":
        fp["base_url"] = settings.openai_base_url or ""
    elif provider == "cursor":
        fp["base_url"] = settings.cursor_base_url or ""
    return fp


def fingerprint_to_key_name(fingerprint: Dict[str, Any]) -> str:
    """Stable slug unique to provider/model specs (same tag, different config → different key)."""
    provider = _slug_part(str(fingerprint.get("provider") or "unknown"))
    model = _slug_part(str(fingerprint.get("model") or "unknown").replace(":", "-"))

    if fingerprint.get("provider") == "ollama":
        parts = [
            provider,
            model,
            _slug_part(str(fingerprint.get("family") or "")),
            _slug_part(str(fingerprint.get("parameter_size") or "")),
            _slug_part(str(fingerprint.get("quantization_level") or "")),
        ]
        digest = str(fingerprint.get("digest") or "").strip()
        if digest:
            parts.append(digest.replace(":", "")[:12])
        elif fingerprint.get("parameters"):
            parts.append(_short_hash({"parameters": fingerprint.get("parameters")}))
        return "-".join(part for part in parts if part and part != "unknown")

    if fingerprint.get("provider") in REMOTE_AI_PROVIDERS:
        return f"{provider}-{model}"

    base_url = str(fingerprint.get("base_url") or "").strip()
    suffix = _short_hash({"base_url": base_url}) if base_url else ""
    return f"{provider}-{model}{('-' + suffix) if suffix else ''}"


def _public_show_snapshot(show: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "details": show.get("details"),
        "capabilities": show.get("capabilities"),
        "parameters": parse_modelfile_parameters(str(show.get("modelfile") or "")),
        "modelfile_excerpt": "\n".join(
            line for line in str(show.get("modelfile") or "").splitlines()[:20]
        ),
    }


def ensure_model_registry_entry(
    settings: Settings,
    *,
    models_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Resolve or create ``data/benchmark/models/<key_name>.json`` for the active model.

    Returns the registry document (also written to disk).
    """
    ensure_runtime_dirs()
    root = models_dir or BENCHMARK_MODELS_DIR
    root.mkdir(parents=True, exist_ok=True)

    provider = (settings.ai_provider or "").strip().lower()
    model = (settings.active_model() or "").strip()
    issues: List[str] = []
    show_snapshot: Optional[Dict[str, Any]] = None
    tag_snapshot: Optional[Dict[str, Any]] = None

    try:
        if provider == "ollama":
            if not settings.ollama_base_url:
                raise RuntimeError("OLLAMA_BASE_URL is not configured")
            show = fetch_ollama_show(settings.ollama_base_url, model)
            show_snapshot = _public_show_snapshot(show)
            try:
                tag_snapshot = fetch_ollama_tag_info(settings.ollama_base_url, model)
            except Exception as exc:  # noqa: BLE001
                issues.append(f"tag info unavailable: {exc}")
                tag_snapshot = {}
            fingerprint = build_ollama_fingerprint(
                model=model,
                show=show,
                tag_info=tag_snapshot,
            )
        else:
            fingerprint = build_provider_fingerprint(settings)
    except Exception as exc:  # noqa: BLE001
        issues.append(f"model fingerprint incomplete: {exc}")
        fingerprint = {"provider": provider, "model": model, "fallback": True}
        _log_warning(f"using fallback fingerprint for {provider}/{model}: {exc}")

    key_name = fingerprint_to_key_name(fingerprint)
    path = root / f"{key_name}.json"
    now = _utcnow_iso()

    entry: Dict[str, Any] = {
        "schema_version": MODEL_REGISTRY_SCHEMA_VERSION,
        "key_name": key_name,
        "provider": provider,
        "model": model,
        "fingerprint": fingerprint,
        "show": show_snapshot,
        "tag": tag_snapshot,
        "registry_path": _relative_path(path),
        "issues": issues,
        "created_at": now,
        "updated_at": now,
    }

    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and existing.get("created_at"):
                entry["created_at"] = existing["created_at"]
        except (OSError, json.JSONDecodeError):
            pass

    path.write_text(
        json.dumps(entry, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    _log_info(f"registry entry → {path} ({provider}/{model})")
    return entry


def resolve_model_identity(
    settings: Settings,
    *,
    models_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Return registry entry dict with ``key_name`` for benchmark result storage."""
    entry = ensure_model_registry_entry(settings, models_dir=models_dir)
    return {
        "key_name": entry.get("key_name"),
        "provider": entry.get("provider"),
        "model": entry.get("model"),
        "registry_path": entry.get("registry_path"),
        "fingerprint": entry.get("fingerprint") or {},
        "show": entry.get("show"),
        "tag": entry.get("tag"),
        "issues": entry.get("issues") or [],
    }


def load_model_registry_entry(key_name: str, *, models_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    root = models_dir or BENCHMARK_MODELS_DIR
    path = root / f"{key_name}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
