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

from ramigpt.paths import STATIC_DIR, TEMPLATES_DIR, ensure_runtime_dirs
from ramigpt.web.app import app, socketio, _CERT_FILE, _KEY_FILE

ensure_runtime_dirs()

# Expose Flask app for `flask run` / WSGI servers.
application = app

APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", "8443"))


def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _should_run_startup_side_effects(use_reloader: bool) -> bool:
    """With Werkzeug reloader, only the child process should run one-shot work."""
    if not use_reloader:
        return True
    return os.environ.get("WERKZEUG_RUN_MAIN") == "true"


def _clean_logs_on_startup() -> None:
    """Wipe data/logs on boot (same as the UI broom / POST /api/logs/clean)."""
    from ramigpt.utils.logging import debug_logger
    from ramigpt.utils.session_logging import clear_all_data_logs

    try:
        result = clear_all_data_logs(include_log_files=True)
        removed = result.get("removed", 0)
        path = result.get("path", "")
        print(f"[RamiGPT] Cleared data/logs (removed={removed})", flush=True)
        debug_logger.info(f"logs.clean.startup removed={removed} path={path}")
    except Exception as exc:  # noqa: BLE001
        print(f"[RamiGPT] Failed to clear data/logs: {exc}", flush=True)


def _extra_watch_files() -> list[str]:
    """Watch templates/static so UI edits also trigger a reload."""
    files: list[str] = []
    for root in (TEMPLATES_DIR, STATIC_DIR):
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file():
                files.append(str(path))
    return files


def _silence_eventlet_ssl_noise() -> None:
    """Drop SSL handshake traceback spam from eventlet's hub / WSGI server.

    Happens when a client speaks plain HTTP (or broken TLS) to the HTTPS port —
    not actionable; eventlet otherwise dumps a full stack + 'Removing descriptor'.
    """
    import ssl

    try:
        from eventlet.hubs.hub import BaseHub
        from eventlet import wsgi as eventlet_wsgi
    except ImportError:
        return

    _orig_squelch = BaseHub.squelch_exception

    def _quiet_squelch(self, fileno, exc_info):  # noqa: ANN001
        if isinstance(exc_info[1], ssl.SSLError):
            try:
                self.remove_descriptor(fileno)
            except Exception:
                pass
            return
        return _orig_squelch(self, fileno, exc_info)

    BaseHub.squelch_exception = _quiet_squelch

    _orig_process = eventlet_wsgi.Server.process_request

    def _quiet_process_request(self, conn_state):  # noqa: ANN001
        try:
            return _orig_process(self, conn_state)
        except ssl.SSLError:
            try:
                conn_state[1].close()
            except Exception:
                pass

    eventlet_wsgi.Server.process_request = _quiet_process_request


if __name__ == "__main__":
    # Default on for local development; set APP_RELOAD=0 to disable.
    use_reloader = _env_flag("APP_RELOAD", "1")
    if use_reloader:
        app.config["TEMPLATES_AUTO_RELOAD"] = True
        print(
            f"[RamiGPT] Auto-reload enabled on https://{APP_HOST}:{APP_PORT}",
            flush=True,
        )

    # Default on; set APP_CLEAN_LOGS_ON_START=0 to keep previous session logs.
    if _should_run_startup_side_effects(use_reloader) and _env_flag(
        "APP_CLEAN_LOGS_ON_START", "1"
    ):
        _clean_logs_on_startup()

    _silence_eventlet_ssl_noise()
    socketio.run(
        app,
        host=APP_HOST,
        port=APP_PORT,
        debug=False,
        use_reloader=use_reloader,
        reloader_options={
            "extra_files": _extra_watch_files(),
            "exclude_patterns": [
                "*/data/*",
                "*/.git/*",
                "*/venv/*",
                "*/__pycache__/*",
                "*/.cursor/*",
                "*/certs/*",
                "*.pyc",
                "*.log",
            ],
        },
        keyfile=_KEY_FILE,
        certfile=_CERT_FILE,
        allow_unsafe_werkzeug=True,
        log_output=False,
    )
