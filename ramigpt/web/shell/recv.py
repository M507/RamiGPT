"""Low-level PTY receive helpers."""

from __future__ import annotations

import time

from ramigpt.web.state import timeout_default


def _require_live_shell(shell, *, where: str = "shell op"):
    """Raise a clear error instead of AttributeError on a dead/missing tube."""
    if shell is None:
        raise RuntimeError(
            f"{where}: SSH shell is None "
            "(process spawn failed, session disconnected, or connect never finished)"
        )
    return shell


def receive_shell_output(shell, prompt_delimiter, timeout_default=0.5, max_timeout=2):
    """ 
    Receives shell output line by line until the prompt delimiter is found 
    or a consecutive timeout of max_timeout seconds occurs.
    """
    shell_output = b""  # Use bytes initially to avoid decoding issues
    consecutive_timeout = 0  # Track consecutive timeout duration

    while True:
        try:
            line = shell.recv(timeout=timeout_default)  # Read small chunks with timeout

            if line:
                shell_output += line  # Append received bytes
                consecutive_timeout = 0  # Reset timeout counter

                # Stop if the prompt delimiter is detected
                if prompt_delimiter.encode() in shell_output:
                    break
            else:
                consecutive_timeout += timeout_default  # Accumulate timeout duration
                if consecutive_timeout >= max_timeout:
                    break  # Stop if timeout exceeds 2 seconds

        except Exception as e:
            break  # Handle unexpected errors gracefully

    return shell_output.decode('utf-8', errors='ignore').strip()  # Decode safely

def recv_for_duration(shell, duration):
    _require_live_shell(shell, where="recv_for_duration")
    end_time = time.time() + duration
    data = b''
    while time.time() < end_time:
        try:
            remaining_time = end_time - time.time()
            if remaining_time <= 0:
                break
            new_data = shell.recv(timeout=remaining_time)
            if new_data:
                data += new_data
        except EOFError:
            break  # Stop if the connection is closed
    return data
def _safe_decode(data) -> str:
    """Decode shell bytes without crashing Full AI on binary/invalid UTF-8."""
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    try:
        return bytes(data).decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return repr(data)
def _interrupt_shell(shell) -> None:
    """Best-effort Ctrl-C to stop a runaway remote command."""
    if shell is None:
        return
    try:
        shell.send(b"\x03")
    except Exception:  # noqa: BLE001
        pass
