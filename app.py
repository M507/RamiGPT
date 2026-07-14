"""
RamiGPT entrypoint.

Run locally:
    python app.py

Docker uses the same module via docker-compose.
"""

from __future__ import annotations

import logging
import os
import sys
import warnings
from pathlib import Path

# Hide third-party / runtime noise before anything else imports.
warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONWARNINGS", "ignore")
os.environ.setdefault("PWNLIB_NOTERM", "1")
logging.captureWarnings(True)
logging.getLogger("py.warnings").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("pwnlib").setLevel(logging.ERROR)

# Ensure the project root is importable when started as a script.
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from ramigpt.paths import ensure_runtime_dirs
from ramigpt.web.app import app, socketio, _CERT_FILE, _KEY_FILE

ensure_runtime_dirs()

# Expose Flask app for `flask run` / WSGI servers.
application = app

APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", "8443"))


if __name__ == "__main__":
    socketio.run(
        app,
        host=APP_HOST,
        port=APP_PORT,
        debug=False,
        keyfile=_KEY_FILE,
        certfile=_CERT_FILE,
        allow_unsafe_werkzeug=True,
        log_output=False,
    )
