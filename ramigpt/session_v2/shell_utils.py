"""PTY prompt / editor / password heuristics for session v2."""

from __future__ import annotations

import re
from typing import Any, Callable, Optional

from ramigpt.domain.root_detection import diagnose_root


def normalize_terminal_text(data: Any) -> str:
    text = "" if data is None else str(data)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def last_line(text: str) -> str:
    lines = normalize_terminal_text(text).split("\n")
    return lines[-1] if lines else ""


def looks_like_editor_stuck(text: str) -> bool:
    lowered = (text or "").lower()
    markers = (
        "type  :qa",
        "type :qa",
        "press <enter> to exit vim",
        "-- insert --",
        "-- replace --",
        "entering ex mode",
        "[no write since last change]",
        "e325: attention",
        "found a swap file",
    )
    return any(marker in lowered for marker in markers)


def looks_like_password_prompt(text: str) -> bool:
    lowered = (text or "").lower()
    return any(
        token in lowered
        for token in (
            "[sudo] password",
            "password for ",
            "password:",
            "passphrase for ",
        )
    )


def still_waiting_on_password(text: str) -> bool:
    line = last_line(text).strip().lower()
    return line.endswith(":") and any(
        token in line for token in ("password", "passphrase")
    )


def looks_like_root_prompt(text: str) -> bool:
    line = last_line(text).strip()
    if not line:
        return False
    if line in {"#", "root#"}:
        return True
    if line.endswith("#") and ("@" in line or ":/" in line or "~" in line):
        return True
    return bool(re.search(r"\[[^\]]+\]#\s*$", line))


def output_indicates_root(hostname: str, text: str) -> bool:
    if diagnose_root(hostname, text).get("got_root"):
        return True
    for line in normalize_terminal_text(text).split("\n")[-8:]:
        if diagnose_root(hostname, line).get("got_root"):
            return True
    return False


def recv_chunk(shell: Any, bridge_recv_for_duration: Callable[..., Any], seconds: float) -> str:
    raw = bridge_recv_for_duration(shell, seconds)
    if isinstance(raw, (bytes, bytearray)):
        text = raw.decode("utf-8", errors="replace")
    elif raw is None:
        text = ""
    else:
        text = str(raw)
    return normalize_terminal_text(text).strip()
