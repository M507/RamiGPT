"""Shared types for Upgraded Session v2."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional


@dataclass
class CommandRunResult:
    """Outcome of executing one AI command against an interactive PTY."""

    shell_output: Optional[str] = None
    shell_output_lines: List[str] = field(default_factory=list)
    last_line: str = ""
    got_root: bool = False
    needs_reconnect: bool = False
    prompt_delimiter: Any = None
    notes: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ShellBridge:
    """
    Thin adapter over the legacy app.py shell helpers.

    Keeps session_v2 free of Flask imports while reusing battle-tested PTY code.
    """

    recv_until_v4: Callable[..., tuple]
    interrupt_shell: Callable[[Any], None]
    is_prompt_line: Callable[[str], bool]
    looks_like_editor_stuck: Callable[[str], bool]
    try_quit_editor: Callable[[Any], str]
    looks_like_password_prompt: Callable[[str], bool]
    still_waiting_on_password: Callable[[str], bool]
    answer_password_prompt: Callable[..., str]
    recv_for_duration: Callable[..., Any]
    safe_decode: Callable[[Any], str]
    sleep: Callable[[float], None]
