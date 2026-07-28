"""Expect-style interactive PTY driver for Upgraded Session v2."""

from __future__ import annotations

import time
from typing import Any, Optional

from ramigpt.session_v2.shell_utils import (
    last_line,
    looks_like_editor_stuck,
    looks_like_password_prompt,
    looks_like_root_prompt,
    normalize_terminal_text,
    output_indicates_root,
    recv_chunk,
    still_waiting_on_password,
)
from ramigpt.session_v2.types import CommandRunResult, ShellBridge

_DEFAULT_TIMEOUT = 12.0
_ROOT_FOLLOWUP = 'id; cat /root/flag.txt 2>/dev/null; whoami'
_NESTED_EXIT = "exit"


class InteractiveSessionDriver:
    """
    Drive a persistent remote shell through common interactive states.

    Handles password prompts, editor TUIs, and nested root shells proactively
    instead of waiting for a hang timeout and reconnecting.
    """

    def __init__(
        self,
        *,
        bridge: ShellBridge,
        hostname: str,
        password: str,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._bridge = bridge
        self._hostname = hostname or ""
        self._password = password or ""
        self._timeout = max(float(timeout or 0), 8.0)

    def execute(self, shell: Any, command: str) -> CommandRunResult:
        notes: list[str] = []
        shell.sendline(command)
        deadline = time.time() + self._timeout
        buffer = ""
        sent_root_followup = False
        sent_nested_exit = False

        while time.time() < deadline:
            chunk = recv_chunk(shell, self._bridge.recv_for_duration, 0.35)
            if chunk:
                buffer = normalize_terminal_text(f"{buffer}\n{chunk}".strip())

            if output_indicates_root(self._hostname, buffer):
                notes.append("root_detected_during_drive")
                return self._result(buffer, notes=notes)

            if looks_like_password_prompt(buffer) and still_waiting_on_password(buffer):
                notes.append("answered_password_prompt")
                self._bridge.answer_password_prompt(shell, {"password": self._password}, None)
                self._bridge.sleep(0.25)
                continue

            if looks_like_editor_stuck(buffer):
                notes.append("quit_interactive_editor")
                quit_text = self._bridge.try_quit_editor(shell)
                if quit_text:
                    buffer = normalize_terminal_text(f"{buffer}\n{quit_text}".strip())
                self._bridge.sleep(0.2)
                continue

            if looks_like_root_prompt(buffer) and not sent_root_followup:
                notes.append("root_shell_followup")
                shell.sendline(_ROOT_FOLLOWUP)
                sent_root_followup = True
                self._bridge.sleep(0.35)
                continue

            if sent_root_followup and looks_like_root_prompt(buffer) and not sent_nested_exit:
                notes.append("nested_shell_exit")
                shell.sendline(_NESTED_EXIT)
                sent_nested_exit = True
                self._bridge.sleep(0.25)
                continue

            prompt = last_line(buffer)
            if buffer and self._bridge.is_prompt_line(prompt):
                notes.append("prompt_restored")
                return self._result(buffer, notes=notes)

            self._bridge.sleep(0.05)

        return self._recover_after_timeout(shell, command, buffer, notes)

    def _recover_after_timeout(
        self,
        shell: Any,
        command: str,
        buffer: str,
        notes: list[str],
    ) -> CommandRunResult:
        notes.append("timeout_hang_recovery")
        self._bridge.interrupt_shell(shell)
        self._bridge.sleep(0.2)
        self._bridge.interrupt_shell(shell)
        drained = recv_chunk(shell, self._bridge.recv_for_duration, 2.0)
        combined = normalize_terminal_text(f"{buffer}\n{drained}".strip())

        if output_indicates_root(self._hostname, combined):
            notes.append("root_detected_after_recovery")
            return self._result(combined, notes=notes)

        if looks_like_editor_stuck(combined):
            notes.append("editor_recovery")
            quit_text = self._bridge.try_quit_editor(shell)
            if quit_text:
                combined = normalize_terminal_text(f"{combined}\n{quit_text}".strip())

        if looks_like_password_prompt(combined) and still_waiting_on_password(combined):
            notes.append("password_recovery")
            after_pw = self._bridge.answer_password_prompt(
                shell, {"password": self._password}, None
            )
            combined = normalize_terminal_text(f"{combined}\n{after_pw}".strip())

        prompt = last_line(combined)
        if self._bridge.is_prompt_line(prompt):
            notes.append("prompt_after_recovery")
            return self._result(combined, notes=notes)

        return CommandRunResult(
            shell_output=combined or None,
            shell_output_lines=combined.split("\n") if combined else [],
            last_line=prompt,
            got_root=output_indicates_root(self._hostname, combined),
            needs_reconnect=True,
            notes=notes,
        )

    def _result(self, text: str, *, notes: list[str]) -> CommandRunResult:
        lines = text.split("\n") if text else []
        return CommandRunResult(
            shell_output=text or None,
            shell_output_lines=lines,
            last_line=last_line(text),
            got_root=output_indicates_root(self._hostname, text),
            needs_reconnect=False,
            notes=notes,
        )
