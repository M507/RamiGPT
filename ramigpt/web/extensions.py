"""Flask app, server-side sessions, and Socket.IO."""

from __future__ import annotations

from flask import Flask
from flask_session import Session
from flask_socketio import SocketIO

from ramigpt.paths import CERTS_DIR, SESSIONS_DIR, STATIC_DIR, TEMPLATES_DIR

CERT_FILE = str(CERTS_DIR / "cert.pem")
KEY_FILE = str(CERTS_DIR / "key.pem")

app = Flask(
    __name__,
    template_folder=str(TEMPLATES_DIR),
    static_folder=str(STATIC_DIR),
    static_url_path="/static",
)
app.config["SECRET_KEY"] = "your_secret_key"
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = str(SESSIONS_DIR / "flask_session")
Session(app)

socketio = SocketIO(app, ssl_context=(CERT_FILE, KEY_FILE))

# Backward-compatible aliases used by root app.py
_CERT_FILE = CERT_FILE
_KEY_FILE = KEY_FILE
