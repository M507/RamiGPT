"""Sleep helpers safe on Socket.IO greenlets and OS threads."""

from __future__ import annotations

import threading
import time

from ramigpt.web.extensions import socketio
from ramigpt.web.state import _ai_tls

def _ai_sleep(seconds: float) -> None:
    """Sleep that is safe both on the eventlet hub and on OS threads."""
    if getattr(_ai_tls, "use_time_sleep", False):
        time.sleep(seconds)
        return
    try:
        socketio.sleep(seconds)
    except Exception:  # noqa: BLE001
        time.sleep(seconds)


def _wait_or_stop(stop_flag: threading.Event, seconds: float) -> bool:
    """Wait up to ``seconds``; return True if stop was requested (possibly early).

    Used between Full AI iterations so Stop wakes the inter-request delay instead
    of letting the next LLM call start after a blind sleep.
    """
    if stop_flag.is_set():
        return True
    if getattr(_ai_tls, "use_time_sleep", False):
        return bool(stop_flag.wait(timeout=seconds))
    deadline = time.monotonic() + max(0.0, float(seconds))
    while True:
        if stop_flag.is_set():
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return bool(stop_flag.is_set())
        _ai_sleep(min(0.05, remaining))
