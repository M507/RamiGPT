"""Per-session logging so hang/breakage analysis is isolated from global debug.log.

Layout (one folder per connect / reconnect so debugging stays easy):

  data/logs/sessions/<session_id>/
    runs.index                 — chronologic index of runs
    latest                     — text pointer to the active run directory name
    001_20260714T143019Z_connect/
      session.log
      events.jsonl
      breakages/
    002_20260714T145512Z_reconnect/
      ...
"""

from __future__ import annotations

import json
import logging
import re
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from ramigpt.paths import LOGS_DIR, ensure_runtime_dirs

_lock = threading.RLock()
_loggers: Dict[str, "SessionLogger"] = {}
# Live terminal scrollback (survives browser refresh while the app is up).
_MAX_TERMINAL_LINES = 2500
_terminal_buffers: Dict[str, Deque[Dict[str, Any]]] = {}
_terminal_seeded: set = set()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_session_dir_name(session_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", (session_id or "").strip())
    return cleaned or "unknown-session"


def _safe_reason(reason: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", (reason or "run").strip().lower())
    return cleaned or "run"


class SessionLogger:
    """
    Active writer for one inventory session_id. Call begin_run() on each
    connect / reconnect so every conversation gets a fresh pair of files.
    """

    def __init__(self, session_id: str) -> None:
        ensure_runtime_dirs()
        self.session_id = session_id
        self.session_dir = LOGS_DIR / "sessions" / _safe_session_dir_name(session_id)
        self.session_dir.mkdir(parents=True, exist_ok=True)

        self.run_dir: Optional[Path] = None
        self.run_id: Optional[str] = None
        self.run_reason: Optional[str] = None
        self.events_path: Optional[Path] = None
        self._breakage_index = 0
        self._last_ui: Optional[str] = None
        self._run_index = 0

        self._logger = logging.getLogger(
            f"SessionLogger.{_safe_session_dir_name(session_id)}"
        )
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False
        self._close_handlers()

        # Resume the last active run if present; otherwise wait for begin_run()
        # (called on connect / reconnect) so we don't create an empty "boot" folder.
        latest = self._read_latest_name()
        if latest and (self.session_dir / latest).is_dir():
            self._attach_run_dir(self.session_dir / latest, reason="resume")

    def _read_latest_name(self) -> Optional[str]:
        pointer = self.session_dir / "latest"
        try:
            name = pointer.read_text(encoding="utf-8").strip()
            return name or None
        except FileNotFoundError:
            return None
        except Exception:  # noqa: BLE001
            return None

    def _write_latest_name(self, run_name: str) -> None:
        pointer = self.session_dir / "latest"
        pointer.write_text(run_name + "\n", encoding="utf-8")

    def _next_run_index(self) -> int:
        existing = [
            p.name
            for p in self.session_dir.iterdir()
            if p.is_dir() and re.match(r"^\d{3}_", p.name)
        ]
        if not existing:
            return 1
        nums = []
        for name in existing:
            try:
                nums.append(int(name.split("_", 1)[0]))
            except ValueError:
                continue
        return (max(nums) if nums else 0) + 1

    def _close_handlers(self) -> None:
        for handler in list(self._logger.handlers):
            try:
                handler.flush()
                handler.close()
            except Exception:  # noqa: BLE001
                pass
            try:
                self._logger.removeHandler(handler)
            except Exception:  # noqa: BLE001
                pass

    def _attach_run_dir(self, run_dir: Path, *, reason: str) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "breakages").mkdir(exist_ok=True)

        self.run_dir = run_dir
        self.run_id = run_dir.name
        self.run_reason = reason
        self.events_path = run_dir / "events.jsonl"
        self._breakage_index = 0
        self._last_ui = None

        self._close_handlers()
        handler = logging.FileHandler(run_dir / "session.log", encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        self._logger.addHandler(handler)

    def begin_run(self, reason: str = "connect") -> "SessionLogger":
        """
        Start a new conversation log folder (new session.log + events.jsonl).
        Use reason="connect" or "reconnect" (or any short label).
        """
        reason_s = _safe_reason(reason)
        with _lock:
            idx = self._next_run_index()
            self._run_index = idx
            run_name = f"{idx:03d}_{_stamp()}_{reason_s}"
            run_dir = self.session_dir / run_name
            self._attach_run_dir(run_dir, reason=reason_s)
            self._write_latest_name(run_name)

            index_path = self.session_dir / "runs.index"
            with index_path.open("a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "ts": _utcnow(),
                            "index": idx,
                            "reason": reason_s,
                            "run": run_name,
                            "session_id": self.session_id,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

        # Outside the lock (event re-enters the RLock for jsonl append).
        self.info(f"=== NEW LOG RUN #{idx} reason={reason_s} dir={run_name} ===")
        self.event(
            "LOG_RUN_START",
            f"Started log run #{idx} ({reason_s})",
            run=run_name,
            reason=reason_s,
            index=idx,
        )
        return self

    def _ensure_run(self) -> None:
        if self.run_dir is None or not self._logger.handlers:
            self.begin_run("adhoc")

    # ------------------------------------------------------------------ logging

    def _flush(self) -> None:
        for h in self._logger.handlers:
            try:
                h.flush()
            except Exception:  # noqa: BLE001
                pass

    def debug(self, message: str) -> None:
        self._ensure_run()
        self._logger.debug(message)
        self._flush()

    def info(self, message: str) -> None:
        self._ensure_run()
        self._logger.info(message)
        self._flush()

    def warning(self, message: str) -> None:
        self._ensure_run()
        self._logger.warning(message)
        self._flush()

    def error(self, message: str) -> None:
        self._ensure_run()
        self._logger.error(message)
        self._flush()

    def exception(self, message: str) -> None:
        self._ensure_run()
        self._logger.exception(message)
        self._flush()

    def block(self, title: str, body: str = "", level: int = logging.INFO) -> None:
        """Write a readable multi-line section to session.log."""
        self._ensure_run()
        sep = "=" * 72
        text = body if body is not None else ""
        if text and not text.endswith("\n"):
            text = text + "\n"
        payload = f"{sep}\n[{title}]\n{text}{sep}"
        self._logger.log(level, payload)
        self._flush()

    def _append_event(self, payload: Dict[str, Any]) -> None:
        if self.events_path is None:
            return
        line = json.dumps(payload, ensure_ascii=False, default=str)
        with _lock:
            with self.events_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
                fh.flush()

    def event(self, kind: str, message: str, **details: Any) -> Dict[str, Any]:
        payload = {
            "ts": _utcnow(),
            "session_id": self.session_id,
            "run": self.run_id,
            "kind": kind,
            "message": message,
            "details": details or {},
        }
        self._append_event(payload)

        kind_u = kind.upper()
        level = logging.WARNING if kind_u in {
            "BREAKAGE", "RECONNECT_FAILED", "RECONNECT_EXHAUSTED", "ERROR", "ROOT_MISS"
        } else logging.INFO
        if kind_u in {"ROOT", "RECONNECT_OK"}:
            level = logging.INFO

        detail_lines = []
        for key, value in (details or {}).items():
            rendered = value if isinstance(value, str) else json.dumps(
                value, ensure_ascii=False, default=str, indent=2
            )
            detail_lines.append(f"{key}:\n{rendered}")
        body = message if not detail_lines else message + "\n\n" + "\n\n".join(detail_lines)
        self.block(kind_u, body, level=level)
        return payload

    def ui(self, message: str, *, color: Optional[str] = None) -> None:
        """Mirror a UI-facing line into session.log + terminal history."""
        text = message if isinstance(message, str) else str(message)
        if self._last_ui == text:
            return
        self._last_ui = text
        self.info(f"[UI] {text}")
        record_terminal_line(self.session_id, text, color=color)

    def ai_turn(
        self,
        *,
        request_n: int,
        system: str,
        prompt: str,
        raw_response: str,
        filtered_command: str,
        source: str = "full_ai",
        model: str = "",
        provider: str = "",
    ) -> None:
        meta = []
        if provider:
            meta.append(f"provider: {provider}")
        if model:
            meta.append(f"model: {model}")
        self.block(
            f"AI_TURN #{request_n} ({source})",
            "\n".join(
                [
                    *meta,
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
        prompt_for_events = prompt or ""
        if len(prompt_for_events) > 4000:
            prompt_for_events = (
                prompt_for_events[:1500]
                + f"\n…[truncated prompt {len(prompt or '')} chars]…\n"
                + prompt_for_events[-1500:]
            )
        self._append_event(
            {
                "ts": _utcnow(),
                "session_id": self.session_id,
                "run": self.run_id,
                "kind": "AI_TURN",
                "message": f"request#{request_n}",
                "details": {
                    "source": source,
                    "provider": provider or None,
                    "model": model or None,
                    "system": system,
                    "prompt": prompt_for_events,
                    "prompt_chars": len(prompt or ""),
                    "raw_response": raw_response,
                    "filtered_command": filtered_command,
                },
            }
        )

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
        self._append_event(
            {
                "ts": _utcnow(),
                "session_id": self.session_id,
                "run": self.run_id,
                "kind": "SHELL_IO",
                "message": f"request#{request_n}",
                "details": {
                    "source": source,
                    "command": command,
                    "shell_output": output if output is not None else None,
                    "note": note,
                },
            }
        )

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
        if self.run_dir is None:
            self.begin_run("breakage")
        assert self.run_dir is not None
        self._breakage_index += 1
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.run_dir / "breakages" / f"{self._breakage_index:03d}_{stamp}.txt"
        body = [
            f"session_id: {self.session_id}",
            f"run: {self.run_id}",
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


def record_terminal_line(
    session_id: str,
    text: str,
    *,
    color: Optional[str] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    """Append a line to the live terminal buffer and (optionally) events.jsonl."""
    key = session_id or "unknown"
    _seed_terminal_buffer_from_disk(key)
    entry = {
        "ts": _utcnow(),
        "text": "" if text is None else str(text),
        "color": color or "#00ff00",
    }
    with _lock:
        buf = _terminal_buffers.get(key)
        if buf is None:
            buf = deque(maxlen=_MAX_TERMINAL_LINES)
            _terminal_buffers[key] = buf
        buf.append(entry)
    if persist:
        try:
            slog = get_session_logger(key)
            if slog.events_path is not None:
                slog._append_event(
                    {
                        "ts": entry["ts"],
                        "session_id": key,
                        "run": slog.run_id,
                        "kind": "TERMINAL",
                        "message": entry["text"][:200],
                        "details": {
                            "text": entry["text"],
                            "color": entry["color"],
                        },
                    }
                )
        except Exception:  # noqa: BLE001
            pass
    return entry


def clear_terminal_buffer(session_id: str) -> None:
    with _lock:
        key = session_id or "unknown"
        _terminal_buffers.pop(key, None)
        _terminal_seeded.discard(key)


def _seed_terminal_buffer_from_disk(session_id: str) -> None:
    """Load prior-run scrollback once so live emit does not drop older history."""
    key = session_id or "unknown"
    with _lock:
        if key in _terminal_seeded:
            return
        disk = _load_terminal_from_events(key, _MAX_TERMINAL_LINES)
        live = list(_terminal_buffers.get(key) or ())
        if disk and not live:
            _terminal_buffers[key] = deque(disk, maxlen=_MAX_TERMINAL_LINES)
        elif disk and live:
            _terminal_buffers[key] = deque(disk + live, maxlen=_MAX_TERMINAL_LINES)
        _terminal_seeded.add(key)


def _event_to_terminal_line(ev: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map one events.jsonl record to a terminal line (TERMINAL or legacy kinds)."""
    kind = (ev.get("kind") or "").upper()
    details = ev.get("details") or {}
    if kind == "TERMINAL":
        return {
            "ts": ev.get("ts") or "",
            "text": details.get("text") or ev.get("message") or "",
            "color": details.get("color") or "#00ff00",
        }
    if kind == "CONNECT":
        return {
            "ts": ev.get("ts") or "",
            "text": ev.get("message") or "[*] Connected",
            "color": "#58a6ff",
        }
    if kind == "DISCONNECT":
        return {
            "ts": ev.get("ts") or "",
            "text": ev.get("message") or "[*] Disconnected",
            "color": "#8b949e",
        }
    if kind == "SHELL_IO":
        # Handled specially (may yield two lines) — callers use _shell_io_lines.
        return None
    if kind in {
        "BEROOT_START",
        "BEROOT_OK",
        "BEROOT_FAILED",
        "BEROOT_FULL_AI",
        "FULL_AI_START",
        "FULL_AI_END",
        "FULL_AI_STOP",
        "BREAKAGE",
        "RECONNECT_OK",
        "RECONNECT_ATTEMPT",
        "ROOT",
        "ERROR",
    }:
        msg = ev.get("message") or kind
        color = "#f85149" if kind in {"BREAKAGE", "ERROR", "BEROOT_FAILED"} else "#58a6ff"
        if kind == "ROOT":
            color = "#ff0000"
            msg = "pwned!"
        return {"ts": ev.get("ts") or "", "text": msg, "color": color}
    return None


def _shell_io_lines(ev: Dict[str, Any]) -> List[Dict[str, Any]]:
    details = ev.get("details") or {}
    cmd = details.get("command") or ""
    out = details.get("shell_output") or ""
    lines: List[Dict[str, Any]] = []
    ts = ev.get("ts") or ""
    if cmd:
        lines.append({"ts": ts, "text": f"$ {cmd}", "color": "#00ff00"})
    if out:
        lines.append({"ts": ts, "text": out, "color": "#00ff00"})
    return lines


def _lines_from_events_file(path: Path) -> List[Dict[str, Any]]:
    """
    Parse one events.jsonl into terminal lines.

    If the file already has TERMINAL events, use only those (authoritative UI
    scrollback). Otherwise rebuild from older event kinds.
    """
    terminal: List[Dict[str, Any]] = []
    legacy: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    ev = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                kind = (ev.get("kind") or "").upper()
                if kind == "TERMINAL":
                    line = _event_to_terminal_line(ev)
                    if line:
                        terminal.append(line)
                    continue
                if kind == "SHELL_IO":
                    legacy.extend(_shell_io_lines(ev))
                    continue
                line = _event_to_terminal_line(ev)
                if line:
                    legacy.append(line)
    except OSError:
        return []
    return terminal if terminal else legacy


def _load_terminal_from_events(session_id: str, limit: int) -> List[Dict[str, Any]]:
    """Rebuild scrollback from all run events.jsonl files (after app restart)."""
    session_dir = LOGS_DIR / "sessions" / _safe_session_dir_name(session_id)
    if not session_dir.is_dir():
        return []
    run_dirs = sorted(
        p
        for p in session_dir.iterdir()
        if p.is_dir() and re.match(r"^\d{3}_", p.name)
    )
    lines: List[Dict[str, Any]] = []
    for run_dir in run_dirs:
        events_path = run_dir / "events.jsonl"
        if events_path.is_file():
            lines.extend(_lines_from_events_file(events_path))
    if limit > 0:
        lines = lines[-limit:]
    return lines


def get_terminal_history(session_id: str, *, limit: int = 800) -> List[Dict[str, Any]]:
    """
    Return terminal scrollback for the session.

    Prefers the live in-memory buffer; falls back to events.jsonl after restart.
    """
    key = session_id or "unknown"
    lim = max(1, min(int(limit or 800), _MAX_TERMINAL_LINES))
    _seed_terminal_buffer_from_disk(key)
    with _lock:
        buf = _terminal_buffers.get(key)
        if buf:
            return list(buf)[-lim:]
    return []


def get_session_logger(session_id: str) -> SessionLogger:
    """Return the active logger for this inventory session (current run)."""
    key = session_id or "unknown"
    with _lock:
        if key not in _loggers:
            _loggers[key] = SessionLogger(key)
        return _loggers[key]


def start_session_log_run(session_id: str, reason: str = "connect") -> SessionLogger:
    """
    Open a brand-new log run directory for this session_id.
    Call on every SSH connect and every successful shell reconnect.
    """
    slog = get_session_logger(session_id)
    return slog.begin_run(reason)
