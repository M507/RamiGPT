"""Per-session logging so hang/breakage analysis is isolated from global debug.log."""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from ramigpt.paths import LOGS_DIR, ensure_runtime_dirs

_lock = threading.RLock()
_loggers: Dict[str, "SessionLogger"] = {}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_session_dir_name(session_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", (session_id or "").strip())
    return cleaned or "unknown-session"


class SessionLogger:
    """
    Writes under data/logs/sessions/<session_id>/:

      session.log   — human-readable full timeline (commands, AI, shell, root checks)
      events.jsonl  — machine-readable notable events
      breakages/    — full dumps of each hang / recovery attempt
    """

    def __init__(self, session_id: str) -> None:
        ensure_runtime_dirs()
        self.session_id = session_id
        self.dir = LOGS_DIR / "sessions" / _safe_session_dir_name(session_id)
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "breakages").mkdir(exist_ok=True)

        self._logger = logging.getLogger(f"SessionLogger.{_safe_session_dir_name(session_id)}")
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False
        if not self._logger.handlers:
            handler = logging.FileHandler(self.dir / "session.log", encoding="utf-8")
            handler.setLevel(logging.DEBUG)
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            )
            # Flush every record so the UI/operator can tail mid-run.
            handler.flush = handler.flush  # type: ignore[method-assign]
            self._logger.addHandler(handler)
            self._handler = handler
        else:
            self._handler = self._logger.handlers[0]

        self.events_path = self.dir / "events.jsonl"
        self._breakage_index = 0

    def _flush(self) -> None:
        for h in self._logger.handlers:
            try:
                h.flush()
            except Exception:  # noqa: BLE001
                pass

    def debug(self, message: str) -> None:
        self._logger.debug(message)
        self._flush()

    def info(self, message: str) -> None:
        self._logger.info(message)
        self._flush()

    def warning(self, message: str) -> None:
        self._logger.warning(message)
        self._flush()

    def error(self, message: str) -> None:
        self._logger.error(message)
        self._flush()

    def exception(self, message: str) -> None:
        self._logger.exception(message)
        self._flush()

    def block(self, title: str, body: str = "", level: int = logging.INFO) -> None:
        """Write a readable multi-line section to session.log."""
        sep = "=" * 72
        text = body if body is not None else ""
        if text and not text.endswith("\n"):
            text = text + "\n"
        payload = f"{sep}\n[{title}]\n{text}{sep}"
        self._logger.log(level, payload)
        self._flush()

    def event(self, kind: str, message: str, **details: Any) -> Dict[str, Any]:
        payload = {
            "ts": _utcnow(),
            "session_id": self.session_id,
            "kind": kind,
            "message": message,
            "details": details or {},
        }
        line = json.dumps(payload, ensure_ascii=False, default=str)
        with _lock:
            with self.events_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
                fh.flush()

        kind_u = kind.upper()
        level = logging.WARNING if kind_u in {
            "BREAKAGE", "RECONNECT_FAILED", "RECONNECT_EXHAUSTED", "ERROR", "ROOT_MISS"
        } else logging.INFO
        if kind_u in {"ROOT", "RECONNECT_OK"}:
            level = logging.INFO

        # Human block in session.log (details expanded, not a truncated dict repr).
        detail_lines = []
        for key, value in (details or {}).items():
            rendered = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str, indent=2)
            detail_lines.append(f"{key}:\n{rendered}")
        body = message if not detail_lines else message + "\n\n" + "\n\n".join(detail_lines)
        self.block(kind_u, body, level=level)
        return payload

    def ui(self, message: str) -> None:
        """Mirror a UI-facing line into session.log (compact)."""
        text = message if isinstance(message, str) else str(message)
        # Avoid flooding the log with identical consecutive UI lines.
        if getattr(self, "_last_ui", None) == text:
            return
        self._last_ui = text
        self.info(f"[UI] {text}")

    def ai_turn(
        self,
        *,
        request_n: int,
        system: str,
        prompt: str,
        raw_response: str,
        filtered_command: str,
        source: str = "full_ai",
    ) -> None:
        # Full narrative goes once into session.log; jsonl gets the structured copy.
        self.block(
            f"AI_TURN #{request_n} ({source})",
            "\n".join(
                [
                    f"system: {system}",
                    "",
                    "----- prompt sent to model -----",
                    prompt or "(empty)",
                    "",
                    "----- raw model response -----",
                    raw_response or "(empty)",
                    "",
                    "----- command after filter -----",
                    filtered_command or "(empty)",
                ]
            ),
        )
        payload = {
            "ts": _utcnow(),
            "session_id": self.session_id,
            "kind": "AI_TURN",
            "message": f"request#{request_n}",
            "details": {
                "source": source,
                "system": system,
                "prompt": prompt,
                "raw_response": raw_response,
                "filtered_command": filtered_command,
            },
        }
        with _lock:
            with self.events_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
                fh.flush()

    def shell_io(
        self,
        *,
        request_n: int,
        command: str,
        output: str,
        note: str = "",
        source: str = "full_ai",
    ) -> None:
        self.block(
            f"SHELL_IO #{request_n} ({source})",
            "\n".join(
                [
                    f"note: {note}" if note else "",
                    "----- command executed -----",
                    command or "(empty)",
                    "",
                    "----- shell output -----",
                    output if output is not None else "(None / timeout)",
                ]
            ).lstrip("\n"),
        )
        payload = {
            "ts": _utcnow(),
            "session_id": self.session_id,
            "kind": "SHELL_IO",
            "message": f"request#{request_n}",
            "details": {
                "source": source,
                "command": command,
                "shell_output": output if output is not None else None,
                "note": note,
            },
        }
        with _lock:
            with self.events_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
                fh.flush()

    def root_check(
        self,
        *,
        request_n: int,
        hostname: str,
        last_line: str,
        shell_output: str,
        won: bool,
        reasons: Dict[str, Any],
    ) -> None:
        kind = "ROOT" if won else "ROOT_MISS"
        self.event(
            kind,
            f"request#{request_n} got_root={won}",
            hostname=hostname,
            last_line=last_line,
            shell_output=shell_output,
            diagnosis=reasons,
        )

    def breakage(
        self,
        reason: str,
        *,
        command: str = "",
        shell_output: str = "",
        needs_reconnect: bool = True,
        **extra: Any,
    ) -> Path:
        """
        Record that interactive control was lost ("Start interacting with the shell again").
        Returns path to the written breakage dump file.
        """
        self._breakage_index += 1
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.dir / "breakages" / f"{self._breakage_index:03d}_{stamp}.txt"
        body = [
            f"session_id: {self.session_id}",
            f"utc: {_utcnow()}",
            f"reason: {reason}",
            f"needs_reconnect: {needs_reconnect}",
            f"last_command: {command!r}",
            "",
            "===== shell_output =====",
            shell_output or "(empty)",
            "",
            "===== extra =====",
            json.dumps(extra, indent=2, ensure_ascii=False, default=str),
            "",
        ]
        path.write_text("\n".join(body), encoding="utf-8")
        self.event(
            "BREAKAGE",
            "Start interacting with the shell again — shell hung / prompt lost; needs reconnect",
            reason=reason,
            command=command,
            dump_file=str(path),
            shell_output=shell_output,
            needs_reconnect=needs_reconnect,
            **extra,
        )
        return path


def get_session_logger(session_id: str) -> SessionLogger:
    key = session_id or "unknown"
    with _lock:
        if key not in _loggers:
            _loggers[key] = SessionLogger(key)
        return _loggers[key]
