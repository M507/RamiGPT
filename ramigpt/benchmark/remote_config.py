"""Load pre-existing remote benchmark host credentials from local JSON."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

from ramigpt.paths import BENCHMARK_REMOTE_CONFIG, ensure_runtime_dirs
from ramigpt.utils import debug_logger
from ramigpt.benchmark.tools import normalize_tools

DEFAULT_REMOTE: Dict[str, Any] = {
    "mode": "remote",
    "host": "",
    "port": 22,
    "username": "root",
    "password": "",
    "timeout_seconds": 60,
    "notes": "",
    # Tools run before Full AI on each target (AI always on for benchmark tools path).
    "tools": {"beroot": True},
}


def remote_config_path() -> Path:
    ensure_runtime_dirs()
    return BENCHMARK_REMOTE_CONFIG


def load_remote_config() -> Dict[str, Any]:
    """
    Read data/benchmark/remote.json if present.

    Returns a normalized dict. Missing file → empty defaults (no password).
    """
    path = remote_config_path()
    cfg = deepcopy(DEFAULT_REMOTE)
    if not path.is_file():
        return cfg
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        debug_logger.warning(f"Failed to read {path}: {exc}")
        return cfg
    if not isinstance(raw, dict):
        return cfg

    cfg["mode"] = str(raw.get("mode") or "remote").strip().lower() or "remote"
    cfg["host"] = str(raw.get("host") or "").strip()
    try:
        cfg["port"] = int(raw.get("port") or 22)
    except (TypeError, ValueError):
        cfg["port"] = 22
    cfg["username"] = str(raw.get("username") or "root").strip()
    cfg["password"] = str(raw.get("password") or "")
    try:
        cfg["timeout_seconds"] = int(raw.get("timeout_seconds") or 60)
    except (TypeError, ValueError):
        cfg["timeout_seconds"] = 60
    cfg["notes"] = str(raw.get("notes") or "")
    if "tools" in raw:
        cfg["tools"] = normalize_tools(raw.get("tools"))
    else:
        cfg["tools"] = normalize_tools(None)
    return cfg


def public_remote_config(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Safe copy for the UI / status API (password masked)."""
    data = deepcopy(cfg if cfg is not None else load_remote_config())
    password = data.get("password") or ""
    data["password_set"] = bool(password)
    data["password"] = password  # UI needs to prefill; still local-only app
    data["config_path"] = str(remote_config_path())
    data["config_exists"] = remote_config_path().is_file()
    return data


def merge_remote_override(override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Start with local JSON defaults, then apply any fields supplied by the API body.
    Empty override values do not wipe the file defaults.
    """
    base = load_remote_config()
    if not override:
        return {
            "host": base["host"],
            "port": int(base["port"] or 22),
            "username": base["username"],
            "password": base["password"],
        }
    host = str(override.get("host") or "").strip() or base["host"]
    username = str(override.get("username") or "").strip() or base["username"]
    password = override.get("password")
    if password is None or str(password) == "":
        password = base["password"]
    else:
        password = str(password)
    try:
        port = int(override.get("port") if override.get("port") not in (None, "") else base["port"])
    except (TypeError, ValueError):
        port = int(base["port"] or 22)
    return {
        "host": host,
        "port": port,
        "username": username,
        "password": password,
    }
