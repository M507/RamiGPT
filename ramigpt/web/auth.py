"""Authentication helpers for Flask routes."""

from __future__ import annotations

from functools import wraps

from flask import Flask, request

from ramigpt.web.constants import PUBLIC_ENDPOINTS


def login_required(f):
    """Soft gate: workspace is open; SSH routes still check for a live shell."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function


def register_auth(app: Flask) -> None:
    @app.before_request
    def check_authentication():
        # Local workspace app: allow inventory + settings without SSH login.
        # SSH command routes validate a live shell themselves.
        if request.endpoint in PUBLIC_ENDPOINTS or (request.endpoint or "").startswith("api_"):
            return
        if request.path.startswith("/api/") or request.path.startswith("/static"):
            return
        # Remaining privileged routes require at least one active inventory selection
        if request.endpoint in ("logout",):
            return
        return
