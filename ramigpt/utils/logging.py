"""
Global (process-wide) logging.

Roles — keep these separate from per-session run logs:

  data/logs/debug.log
      Application / process diagnostics: HTTP handlers, SSH connect plumbing,
      benchmark deploy, unexpected exceptions. Compact, NO full AI prompts,
      shell transcripts, or root-diagnosis dumps (those belong under
      data/logs/sessions/<id>/<run>/ or
      data/logs/sessions/benchmarks/<run_id>/<target>/).
      Benchmark lines include the concrete suite / events.jsonl path.

  data/logs/times.log
      Wall-clock metrics only (Full AI runs, benchmarks). One readable block
      per completed timing span — not a chat transcript.

  data/logs/sessions/<session_id>/<run>/
      Workspace conversation logs: AI turns, shell I/O, root checks, breakages.

  data/logs/sessions/benchmarks/<benchmark_run_id>/
      One folder per benchmark suite. run.json + run.log at the suite root;
      each target has its own <target_id>/<run>/events.jsonl tree.
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict, Optional

from ramigpt.paths import LOGS_DIR, ensure_runtime_dirs

ensure_runtime_dirs()

_handler_lock = threading.RLock()


def setup_logger(name: str, file: str, level: int, format: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False
    with _handler_lock:
        if not logger.handlers:
            handler = logging.FileHandler(file, encoding="utf-8")
            handler.setLevel(level)
            handler.setFormatter(logging.Formatter(format))
            logger.addHandler(handler)
    return logger


def _flush(logger: logging.Logger) -> None:
    for h in logger.handlers:
        try:
            h.flush()
        except Exception:  # noqa: BLE001
            pass


time_logger = setup_logger(
    "TimeLogger",
    str(LOGS_DIR / "times.log"),
    logging.INFO,
    "%(asctime)s %(levelname)s %(message)s",
)
debug_logger = setup_logger(
    "DebugLogger",
    str(LOGS_DIR / "debug.log"),
    logging.INFO,  # DEBUG opt-in via RAMIGPT_DEBUG=1 — avoids duplicating session logs
    "%(asctime)s %(levelname)s %(message)s",
)

if os.getenv("RAMIGPT_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
    debug_logger.setLevel(logging.DEBUG)
    for _h in debug_logger.handlers:
        _h.setLevel(logging.DEBUG)


def log_app(message: str, *, level: int = logging.INFO, **fields: Any) -> None:
    """Structured one-liner for process-level events (no session transcripts)."""
    if fields:
        extras = " ".join(f"{k}={fields[k]!r}" for k in sorted(fields))
        message = f"{message} | {extras}"
    debug_logger.log(level, message)
    _flush(debug_logger)


def log_app_exception(message: str, **fields: Any) -> None:
    if fields:
        extras = " ".join(f"{k}={fields[k]!r}" for k in sorted(fields))
        message = f"{message} | {extras}"
    debug_logger.exception(message)
    _flush(debug_logger)


class GlobalTimer:
    """
    Per-key wall-clock timer. Writes ONLY to times.log (not session logs).

    Prefer key=session_id for Full AI spans so concurrent sessions do not collide.
    """

    _lock = threading.RLock()
    _starts: Dict[str, datetime] = {}
    _meta: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def start(key: str = "default", **meta: Any) -> None:
        with GlobalTimer._lock:
            GlobalTimer._starts[key] = datetime.now()
            GlobalTimer._meta[key] = dict(meta or {})

    @staticmethod
    def stop(
        key: str = "default",
        *,
        label: str = "",
        outcome: str = "",
        **extra: Any,
    ) -> Optional[float]:
        with GlobalTimer._lock:
            start = GlobalTimer._starts.pop(key, None)
            meta = GlobalTimer._meta.pop(key, {})
        if start is None:
            debug_logger.warning(f"timer.stop without start key={key!r} label={label!r}")
            _flush(debug_logger)
            return None

        end = datetime.now()
        elapsed = end - start
        elapsed_s = elapsed.total_seconds()
        fields = {**meta, **extra}
        if outcome:
            fields["outcome"] = outcome
        if label:
            fields.setdefault("label", label)
        fields.setdefault("key", key)

        detail_lines = [f"{k}: {fields[k]}" for k in sorted(fields)]
        start_s = start.isoformat(timespec="seconds")
        end_s = end.isoformat(timespec="seconds")
        body = "\n".join(
            [
                f"start: {start_s}",
                f"end:   {end_s}",
                f"elapsed: {elapsed} ({elapsed_s:.3f}s)",
                "",
                *detail_lines,
            ]
        )
        sep = "=" * 72
        title = (label or "TIMING").upper().replace(" ", "_")
        time_logger.info(f"{sep}\n[{title}]\n{body}\n{sep}")
        _flush(time_logger)
        return elapsed_s


def reset_global_log_files() -> None:
    """Truncate debug.log and times.log and reattach handlers."""
    for path in (LOGS_DIR / "debug.log", LOGS_DIR / "times.log"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    for logger, filename in ((debug_logger, "debug.log"), (time_logger, "times.log")):
        with _handler_lock:
            for h in list(logger.handlers):
                try:
                    h.close()
                except Exception:  # noqa: BLE001
                    pass
                logger.removeHandler(h)
            handler = logging.FileHandler(str(LOGS_DIR / filename), encoding="utf-8")
            handler.setLevel(logger.level)
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            logger.addHandler(handler)
    debug_logger.info(
        "debug.log ready — process diagnostics only "
        "(session transcripts → data/logs/sessions/<id>/<run>/)"
    )
    time_logger.info(
        "times.log ready — wall-clock metrics only (Full AI / benchmark durations)"
    )
    _flush(debug_logger)
    _flush(time_logger)
