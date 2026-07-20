"""Read shell output until a prompt delimiter or line match."""

from __future__ import annotations

import time

from flask import session as flask_session

from ramigpt.session_v2 import ShellBridge
from ramigpt.utils import debug_logger
from ramigpt.web.extensions import app
from ramigpt.web.ai.timing import _ai_sleep
from ramigpt.web.prompt_helpers import _debug_enabled
from ramigpt.web.shell.password import _answer_password_prompt, _looks_like_password_prompt, _still_waiting_on_password
from ramigpt.web.shell.prompt_detect import (
    _is_shell_prompt_line,
    _looks_like_editor_stuck,
    _try_quit_editor,
)
from ramigpt.web.shell.recv import (
    _interrupt_shell,
    _require_live_shell,
    _safe_decode,
    recv_for_duration,
)
from ramigpt.web.state import stop_full_ai_by_session, timeout_default

def shell_recvuntil(shell, prompt_delimiter, drop=False, timeout=timeout_default):
    _require_live_shell(shell, where="shell_recvuntil")
    shell_output_bytes  = shell.recvuntil(prompt_delimiter, drop=False, timeout=timeout_default)
    shell_output_lines  = shell_output_bytes.decode('utf-8').split('\n')
    shell_output        = shell_output_bytes.decode('utf-8').strip()
    shell_output_lines_string = str(shell_output_lines)
    return shell_output_bytes, shell_output_lines, shell_output_lines_string, shell_output

def shell_recvuntil_v2(shell, prompt_delimiter, drop=False, timeout=timeout_default, session = None, emit_func = None):
    _require_live_shell(shell, where="shell_recvuntil_v2")
    shell_output_bytes  = shell.recvuntil(prompt_delimiter, drop=False, timeout=timeout_default)
    shell_output_lines  = shell_output_bytes.decode('utf-8').split('\n')
    shell_output        = shell_output_bytes.decode('utf-8').strip()
    shell_output_lines_string = str(shell_output_lines)
    if f"Password:" in shell_output:
        if emit_func != None:
            if _debug_enabled():
                emit_func('message', {'data': f"[Debug] Password:"}, namespace='/get')
        shell.sendline(session.get('password'))  # Send the sudo password
    if f"password for {session.get('username')}" in shell_output:
        if emit_func != None:
            if _debug_enabled():
                emit_func('message', {'data': f"[Debug] Password:"}, namespace='/get')
        shell.sendline(session.get('password'))
    if emit_func != None:
        if _debug_enabled():
            emit_func('message', {'data': f"[Debug] shell_recvuntil_v2:{shell_output_lines_string}"}, namespace='/get')
    return shell_output_bytes, shell_output_lines, shell_output_lines_string, shell_output

def shell_recvuntil_v3(shell, prompt_delimiter, drop=False, timeout=timeout_default, session=None, emit_func=None):
    _require_live_shell(shell, where="shell_recvuntil_v3")
    try:
        shell_output_bytes = shell.recvuntil(prompt_delimiter, drop=drop, timeout=timeout)
    except TimeoutError:
        # Handle the case where the recvuntil times out, possibly due to a sudo password prompt
        if emit_func:
            emit_func('message', {'data': '[Debug] Timeout occurred, possibly stuck at prompt'}, namespace='/get')
        shell.sendline(session.get('password'))  # Attempt to send the password
        shell_output_bytes = shell.recvuntil(prompt_delimiter, drop=drop, timeout=timeout)  # Try to receive again

    shell_output = shell_output_bytes.decode('utf-8')
    shell_output_lines = shell_output.split('\n')
    shell_output_lines_string = str(shell_output_lines)

    # Additional logging for debug information
    if emit_func:
        if _debug_enabled():
            emit_func('message', {'data': f"[Debug] shell_recvuntil_v2:{shell_output_lines_string}"}, namespace='/get')
    
    return shell_output_bytes, shell_output_lines, shell_output_lines_string, shell_output
def _session_v2_bridge() -> ShellBridge:
    """Wire Upgraded Session v2 to the existing PTY helpers in this module."""
    return ShellBridge(
        recv_until_v4=shell_recvuntil_v4,
        interrupt_shell=_interrupt_shell,
        is_prompt_line=_is_shell_prompt_line,
        looks_like_editor_stuck=_looks_like_editor_stuck,
        try_quit_editor=_try_quit_editor,
        looks_like_password_prompt=_looks_like_password_prompt,
        still_waiting_on_password=_still_waiting_on_password,
        answer_password_prompt=_answer_password_prompt,
        recv_for_duration=recv_for_duration,
        safe_decode=_safe_decode,
        sleep=_ai_sleep,
    )


def shell_recvuntil_v4(shell, prompt_delimiter, drop=False, timeout=timeout_default, session=None, emit_func=None):
    """
    Read until a real shell prompt appears as its own line.

    Does NOT use bare `$` / `#` as byte delimiters — those appear constantly in
    command output and used to desync sessions (see events 008 after grep -r /etc).
    """
    _require_live_shell(shell, where="shell_recvuntil_v4")
    with app.app_context():
        wait = max(float(timeout or 0), 8.0)
        deadline = time.time() + wait
        buf = b""
        session_id = None
        if isinstance(session, dict):
            session_id = session.get("sid")
        stop_flag = (
            stop_full_ai_by_session.get(session_id)
            if session_id
            else None
        )

        while time.time() < deadline:
            if stop_flag is not None and stop_flag.is_set():
                # Caller is stopping Full AI — do not wait out the full timeout.
                return None, None, None, None
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            chunk = b""
            try:
                chunk = shell.recv(timeout=min(0.35, remaining))
            except EOFError:
                break
            except Exception:  # noqa: BLE001
                chunk = b""

            if chunk:
                if not isinstance(chunk, (bytes, bytearray)):
                    chunk = str(chunk).encode("utf-8", errors="replace")
                buf += bytes(chunk)

                text = _safe_decode(buf)
                normalized = text.replace("\r\n", "\n").replace("\r", "\n")
                lines = normalized.split("\n")
                last = lines[-1] if lines else ""
                # Prompt on its own final line (with or without trailing spaces).
                if _is_shell_prompt_line(last):
                    shell_output = text.strip("\0")
                    shell_output_lines = shell_output.split("\n")
                    if emit_func is not None:
                        try:
                            payload = {"data": f"{shell_output}"}
                            if session_id:
                                payload["server_session_id"] = session_id
                                emit_func(
                                    "message",
                                    payload,
                                    namespace="/get",
                                    to=session_id,
                                )
                            else:
                                emit_func(
                                    "message",
                                    payload,
                                    namespace="/get",
                                )
                        except Exception:  # noqa: BLE001
                            pass
                    return buf, shell_output_lines, str(shell_output_lines), shell_output

            _ai_sleep(0.05)

        # Timeout — keep noise out of the UI; hang-recovery / reconnect handles it.
        debug_logger.debug(
            "shell_recvuntil_v4 timeout waiting for prompt "
            f"(buf_chars={len(buf)} session={session_id!r})"
        )
        return None, None, None, None
