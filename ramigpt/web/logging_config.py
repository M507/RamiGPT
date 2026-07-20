"""Web-layer logging helpers (process debug.log + per-session run logs).

Use ``log_app`` / ``log_app_exception`` for one-line process diagnostics (→ debug.log).
Use ``get_session_logger(session_id)`` for conversation transcripts (→ data/logs/sessions/).
Never log passwords or API keys.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from flask import Flask, g, request

from ramigpt.utils import debug_logger, get_session_logger, log_app, log_app_exception

__all__ = [
    "configure_web_loggers",
    "debug_logger",
    "get_session_logger",
    "log_app",
    "log_app_exception",
    "log_http_request",
    "log_socket",
    "log_ssh_lifecycle",
    "register_request_logging",
    "session_event",
]


def configure_web_loggers() -> None:
    """Reduce noisy third-party loggers in the web process."""
    for name in (
        "werkzeug",
        "engineio",
        "socketio",
        "urllib3",
        "paramiko",
        "flask",
        "gevent",
        "eventlet",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)


def log_socket(event: str, **fields: Any) -> None:
    """Socket.IO lifecycle (connect / join / disconnect)."""
    log_app(f"socket.{event}", **fields)


def log_ssh_lifecycle(action: str, session_id: Optional[str], **fields: Any) -> None:
    """SSH connect / shell / listener / close — process log + optional session event."""
    sid = session_id or "unknown"
    log_app(f"ssh.{action}", session_id=sid, **fields)
    if not session_id:
        return
    try:
        get_session_logger(session_id).event(
            action.upper(),
            action.replace("_", " "),
            **{k: v for k, v in fields.items() if k not in {"password"}},
        )
    except Exception as exc:  # noqa: BLE001
        debug_logger.debug(
            f"ssh.session_event_skipped action={action!r} session_id={session_id!r} err={exc}"
        )


def session_event(session_id: str, event: str, message: str, **fields: Any) -> None:
    """Write a structured event to the session run log (no debug.log line)."""
    if not session_id:
        return
    try:
        get_session_logger(session_id).event(event, message, **fields)
    except Exception as exc:  # noqa: BLE001
        debug_logger.debug(
            f"session.event_skipped event={event!r} session_id={session_id!r} err={exc}"
        )


def log_http_request(response) -> None:
    """Log one HTTP request/response line (called from after_request hook)."""
    if request.path.startswith("/static"):
        return response

    elapsed_ms: Optional[float] = None
    start = getattr(g, "_req_start_monotonic", None)
    if start is not None:
        elapsed_ms = round((time.monotonic() - start) * 1000, 1)

    session_id: Optional[str] = None
    try:
        from flask import session as flask_session

        session_id = (
            flask_session.get("active_server_session_id")
            or flask_session.get("sid")
            or getattr(flask_session, "sid", None)
        )
    except Exception:  # noqa: BLE001
        pass

    fields: dict[str, Any] = {
        "method": request.method,
        "path": request.path,
        "status": response.status_code,
    }
    if elapsed_ms is not None:
        fields["ms"] = elapsed_ms
    if session_id:
        fields["session_id"] = str(session_id)
    if request.endpoint:
        fields["endpoint"] = request.endpoint

    level = logging.INFO
    if response.status_code >= 500:
        level = logging.ERROR
    elif response.status_code >= 400:
        level = logging.WARNING

    log_app("http.request", level=level, **fields)
    return response


def register_request_logging(app: Flask) -> None:
    """Attach timing + compact access logs for non-static HTTP routes."""

    @app.before_request
    def _record_request_start():
        g._req_start_monotonic = time.monotonic()

    @app.after_request
    def _log_request(response):
        return log_http_request(response)

    @app.teardown_request
    def _log_unhandled(exc):
        if exc is not None:
            log_app_exception(
                "http.unhandled_exception",
                method=request.method,
                path=request.path,
                endpoint=request.endpoint or "",
            )
