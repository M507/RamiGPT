"""Runtime connection status for in-memory SSH sessions."""

from __future__ import annotations

import threading
from typing import Dict, Optional

# server_session_id -> status string
# disconnected | connecting | connected | error
_statuses: Dict[str, str] = {}
_errors: Dict[str, str] = {}
_lock = threading.RLock()


def set_status(session_id: str, status: str, error: Optional[str] = None) -> None:
    with _lock:
        _statuses[session_id] = status
        if error:
            _errors[session_id] = error
        elif status != "error":
            _errors.pop(session_id, None)


def get_status(session_id: str) -> str:
    with _lock:
        return _statuses.get(session_id, "disconnected")


def get_error(session_id: str) -> str | None:
    with _lock:
        return _errors.get(session_id)


def clear_status(session_id: str) -> None:
    with _lock:
        _statuses.pop(session_id, None)
        _errors.pop(session_id, None)


def all_statuses() -> Dict[str, Dict[str, str]]:
    with _lock:
        out = {}
        for sid, status in _statuses.items():
            item = {"status": status}
            if sid in _errors:
                item["error"] = _errors[sid]
            out[sid] = item
        return out
