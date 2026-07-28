"""Socket.IO namespace handlers."""

from __future__ import annotations

import time

from flask_socketio import emit, join_room, leave_room

from ramigpt.web.extensions import socketio
from ramigpt.web.logging_config import log_socket


@socketio.on("connect", namespace="/get")
def test_connect():
    log_socket("connect", namespace="/get")


@socketio.on("join", namespace="/get")
def on_join(data):
    session_id = (data or {}).get("server_session_id")
    if session_id:
        join_room(session_id)
        log_socket("join", session_id=session_id, namespace="/get")
        emit(
            "message",
            {
                "data": f"[*] Subscribed to session {session_id[:8]}…",
                "color": "#8b949e",
                "server_session_id": session_id,
            },
        )


@socketio.on("leave", namespace="/get")
def on_leave(data):
    session_id = (data or {}).get("server_session_id")
    if session_id:
        leave_room(session_id)
        log_socket("leave", session_id=session_id, namespace="/get")


@socketio.on("disconnect", namespace="/get")
def test_disconnect():
    log_socket("disconnect", namespace="/get")


def send_time():
    while True:
        socketio.sleep(1)
        time_str = time.strftime("%H:%M:%S")
        socketio.emit("message", {"data": "Current time: " + time_str}, namespace="/get")
