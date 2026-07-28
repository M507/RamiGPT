"""Session-scoped Socket.IO emit helpers."""

from __future__ import annotations

from flask import request, session

from ramigpt.utils import debug_logger, get_session_logger
from ramigpt.web.extensions import socketio


def resolve_server_session_id():
    """Active inventory session id from JSON body or Flask session."""
    data = request.get_json(silent=True) or {}
    return (
        data.get("server_session_id")
        or session.get("active_server_session_id")
        or session.get("sid")
        or getattr(session, "sid", None)
    )


def emit_session(session_id, data, color=None):
    # Persist first so a reconnect history reload cannot miss this line while the
    # websocket delivery is still in flight (or dropped because we left the room).
    try:
        if session_id:
            get_session_logger(session_id).ui(str(data), color=color)
    except Exception as exc:  # noqa: BLE001
        debug_logger.debug(
            f"session.ui_log_failed session_id={session_id!r} err={exc}"
        )
    payload = {"data": data, "server_session_id": session_id}
    if color is not None:
        payload["color"] = color
    socketio.emit("message", payload, namespace="/get", to=session_id)
