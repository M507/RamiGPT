"""Shell prompt and editor detection heuristics."""

from __future__ import annotations

import re

from ramigpt.web.ai.timing import _ai_sleep
from ramigpt.web.prompt_helpers import _strip_ansi
from ramigpt.web.shell.recv import _safe_decode, recv_for_duration

def _is_shell_prompt_line(line: str) -> bool:
    """
    True for a real shell prompt on its own line.

    Critical: never treat a lone `$`/`#` byte substring in file dumps as a prompt —
    that desynchronizes the PTY (grep/cat of /etc containing `#` comments).
    """
    raw = (line or "").replace("\r", "")
    s = _strip_ansi(raw).strip()
    if not s or len(s) > 160:
        return False
    # Config / grep false positives
    if any(
        tok in s
        for tok in (
            '"',
            "'",
            "`",
            "\\$",
            "^/",
            "NO_DEL",
            "PATH=",
            "Defaults",
            "matching",
        )
    ):
        return False
    if s in {"$", "#", "%"}:
        return True
    if re.fullmatch(r"(?:bash|sh|zsh|ksh|dash)-[0-9.]+[#$]", s):
        return True
    # user@host:~/path$  or  root@host:/#
    if s.endswith("$") or s.endswith("#"):
        if "@" in s or "~" in s or ":/" in s or s.endswith(" $") or s.endswith(" #"):
            return True
        if re.search(r"\[[^\]]+\][#$]$", s):  # [root@box]#
            return True
    return False


def _interrupt_shell(shell) -> None:
    """Best-effort Ctrl-C to stop a runaway remote command."""
    if shell is None:
        return
    try:
        shell.send(b"\x03")
    except Exception:  # noqa: BLE001
        pass


def _looks_like_editor_stuck(text: str) -> bool:
    """True when drain/output shows an interactive vim/editor UI."""
    t = (text or "").lower()
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
    return any(m in t for m in markers)


def _try_quit_editor(shell) -> str:
    """
    Escape an interactive vim (and similar) then force-quit.
    Returns whatever was drained after the quit attempts.
    """
    if shell is None:
        return ""
    try:
        shell.send(b"\x1b")  # ESC — leave insert / operator-pending
    except Exception:  # noqa: BLE001
        pass
    _ai_sleep(0.15)
    for payload in (b":qa!\r", b":q!\r", b"ZQ", b"\x03"):
        try:
            shell.send(payload)
        except Exception:  # noqa: BLE001
            pass
        _ai_sleep(0.2)
    return _safe_decode(recv_for_duration(shell, 1.5)).strip()
