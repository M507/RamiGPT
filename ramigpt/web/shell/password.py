"""Detect and answer interactive password prompts on the PTY."""

from __future__ import annotations

from ramigpt.web.shell.recv import recv_for_duration

def _looks_like_password_prompt(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return (
        "[sudo] password for" in lower
        or "password for" in lower
        or lower.rstrip().endswith("password:")
        or "\npassword:" in lower
        or lower.strip() == "password:"
    )


def _still_waiting_on_password(text: str) -> bool:
    """
    True only if the shell is *currently* stuck at a password prompt.
    Do not use whole-buffer substring checks — BeRoot follow-up drains often
    contain an earlier `[sudo] password for …` line even after `$` returns.
    """
    if not text:
        return False
    lines = [
        ln.strip()
        for ln in str(text).replace("\r", "\n").split("\n")
        if ln.strip()
    ]
    if not lines:
        return False
    last = lines[-1]
    # Recovered prompt means we are no longer waiting.
    if last in {"$", "#"} or last.endswith("$") or last.endswith("#"):
        return False
    return _looks_like_password_prompt(last)


def _answer_password_prompt(shell, session_data, slog=None) -> str:
    """Send the session password once and drain leftover prompt noise."""
    password = session_data.get("password") or ""
    if slog is not None:
        slog.info("answering password prompt (password not logged)")
    payload = password.encode() if isinstance(password, str) else password
    shell.sendline(payload)
    drained = recv_for_duration(shell, 2)
    return drained.decode("utf-8", errors="replace") if drained else ""
