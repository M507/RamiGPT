"""Non-interactive and fallback remote command execution."""

from __future__ import annotations

import time

from ramigpt.web.shell.connection import _open_ssh_interactive_shell

def _sh_single_quote(value: str) -> str:
    """Escape a string for safe inclusion inside shell single quotes."""
    return "'" + str(value or "").replace("'", "'\"'\"'") + "'"


def _ssh_run_capture(ssh_conn, command: str, *, timeout: int = 60) -> bytes:
    """
    Non-interactive remote exec via ``ssh.run()``.

    Unlike ``ssh.process()``, this does not require a Python interpreter on the
    target just to open the channel — critical for slim lab images.
    """
    if not command:
        raise ValueError("empty remote command")
    try:
        tube = ssh_conn.run(command, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"ssh.run() failed: {exc}") from exc
    if tube is None:
        raise RuntimeError("ssh.run() returned None (SSH session may be dead)")
    try:
        return tube.recvall(timeout=timeout) or b""
    finally:
        try:
            tube.close()
        except Exception:  # noqa: BLE001
            pass


def _ssh_run_or_shell(ssh_conn, command: str, *, timeout: int = 60, slog=None) -> bytes:
    """Prefer ``ssh.run()``; fall back to an interactive shell if run fails."""
    try:
        return _ssh_run_capture(ssh_conn, command, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        if slog is not None:
            slog.warning(f"ssh.run() failed ({exc}); falling back to interactive shell")
        runner = _open_ssh_interactive_shell(ssh_conn)
        try:
            recv_for_duration(runner, 0.5)
            runner.sendline(command.encode() if isinstance(command, str) else command)
            deadline = time.time() + max(5, int(timeout))
            buf = b""
            while time.time() < deadline:
                try:
                    chunk = runner.recv(timeout=2)
                except Exception:  # noqa: BLE001
                    chunk = b""
                if chunk:
                    buf += chunk
            return buf
        finally:
            try:
                runner.close()
            except Exception:  # noqa: BLE001
                pass
