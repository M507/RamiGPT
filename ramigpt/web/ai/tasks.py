"""Background task dispatch for Full AI."""

from __future__ import annotations

import threading

from ramigpt.utils import debug_logger
from ramigpt.web.ai.autonomous import autonomous
from ramigpt.web.ai.timing import _ai_sleep
from ramigpt.web.extensions import socketio
from ramigpt.web.state import _ai_tls, loop, stop_full_ai_by_session

def start_autonomous_task(session_data: dict):
    """
    Start Full AI.

    - UI / Socket.IO greenlets: ``socketio.start_background_task`` (normal path).
    - Benchmark OS worker thread: a real ``threading.Thread`` with ``time.sleep``,
      because ``start_background_task`` / hub spawn from that thread never runs
      (benchmark suite 2336cf67… hung at FULL_AI_REQUESTED with no FULL_AI_START).
    """
    session_id = (session_data or {}).get("sid") or "unknown"
    use_os_thread = bool(
        (session_data or {}).get("use_os_thread")
        or (session_data or {}).get("inline_full_ai")
        or (session_data or {}).get("from_benchmark")
    )

    def _runner() -> None:
        if use_os_thread:
            _ai_tls.use_time_sleep = True
        try:
            autonomous(session_data)
        except Exception:  # noqa: BLE001
            debug_logger.exception(f"full_ai.crash session_id={session_id!r}")
            try:
                loop[session_id] = 0
            except Exception:  # noqa: BLE001
                pass
            try:
                from ramigpt.benchmark.orchestrator import mark_full_ai_finished
                mark_full_ai_finished(session_id)
            except Exception:  # noqa: BLE001
                pass
        finally:
            if use_os_thread:
                _ai_tls.use_time_sleep = False

    if use_os_thread:
        thread = threading.Thread(
            target=_runner,
            name=f"autonomous-{str(session_id)[:8]}",
            daemon=True,
        )
        thread.start()
        debug_logger.info(
            f"full_ai.spawn OS-thread session_id={session_id!r} thread={thread.name}"
        )
        return thread

    socketio.start_background_task(_runner)
    debug_logger.info(
        f"full_ai.spawn socketio.start_background_task session_id={session_id!r}"
    )
    return None
