"""Web presentation layer (Flask, Socket.IO, templates, static assets)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask
    from flask_socketio import SocketIO


def __getattr__(name: str):
    if name == "app":
        from ramigpt.web.app import app as flask_app

        return flask_app
    if name == "socketio":
        from ramigpt.web.app import socketio as sio

        return sio
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
