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

    Happens when a browser tab closes/reloads during a long scan, plain HTTP hits
    the HTTPS port, or TLS is aborted mid-handshake — not actionable; eventlet
    otherwise dumps full stacks and can kill the WSGI accept loop.
    """
    import ssl

    def _is_benign_client_disconnect(exc: BaseException) -> bool:
        if isinstance(exc, ssl.SSLError):
            return True
        if isinstance(exc, ValueError) and "closed or unwrapped SSL" in str(exc):
            return True
        if isinstance(exc, (ConnectionResetError, BrokenPipeError)):
            return True
        if isinstance(exc, OSError):
            # 22=EINVAL (accept after client abort), 54/104=ECONNRESET
            return exc.errno in {22, 54, 104}
        return False

    def _close_quietly(obj) -> None:  # noqa: ANN001
        try:
            obj.close()
        except Exception:
            pass

    try:
        from eventlet.hubs.hub import BaseHub
        from eventlet import wsgi as eventlet_wsgi
        from eventlet.green import ssl as green_ssl
    except ImportError:
        return

    _orig_squelch = BaseHub.squelch_exception

    def _quiet_squelch(self, fileno, exc_info):  # noqa: ANN001
        if _is_benign_client_disconnect(exc_info[1]):
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
        except Exception as exc:
            if not _is_benign_client_disconnect(exc):
                raise
            _close_quietly(conn_state[1])

    eventlet_wsgi.Server.process_request = _quiet_process_request

    _orig_accept = green_ssl.GreenSSLSocket.accept

    def _quiet_green_accept(self):  # noqa: ANN001
        while True:
            try:
                return _orig_accept(self)
            except OSError as exc:
                if exc.errno == 22:
                    # Client dropped during TLS handshake; accept the next client.
                    continue
                raise

    green_ssl.GreenSSLSocket.accept = _quiet_green_accept


def _ensure_ubuntu_requirements_on_startup() -> None:
    """Install missing Ubuntu host packages once at boot (best-effort)."""
    from ramigpt.utils.logging import debug_logger
    from ramigpt.utils.ubuntu_requirements import ensure_ubuntu_requirements

    try:
        result = ensure_ubuntu_requirements(
            install=True,
            log=lambda msg: print(f"[RamiGPT] {msg}", flush=True),
        )
        debug_logger.info(
            f"ubuntu.requirements.startup ok={result.ok} "
            f"installed={result.installed} ansible={result.ansible_detail}"
        )
    except Exception as exc:  # noqa: BLE001
        # Don't block the UI if apt/sudo isn't available — deploy/verify will retry.
        print(f"[RamiGPT] Ubuntu requirements check: {exc}", flush=True)
        debug_logger.warning(f"ubuntu.requirements.startup failed: {exc}")


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

    if _should_run_startup_side_effects(use_reloader) and _env_flag(
        "APP_ENSURE_UBUNTU_REQUIREMENTS", "1"
    ):
        _ensure_ubuntu_requirements_on_startup()

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
