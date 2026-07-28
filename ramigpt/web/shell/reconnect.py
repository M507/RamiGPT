"""Shell reconnect and recreation after PTY breakage."""

from __future__ import annotations

from flask import jsonify, session

from pwn import ssh
import logging

from ramigpt.utils import debug_logger, start_session_log_run
from ramigpt.web.logging_config import log_app, log_ssh_lifecycle
from ramigpt.web.shell.connection import _open_ssh_interactive_shell
from ramigpt.web.shell.recv import recv_for_duration
from ramigpt.web.shell.recvuntil import shell_recvuntil_v2
from ramigpt.web.state import (
    prompt_delimiter,
    prompt_delimiters,
    ssh_shells,
    ssh_ssh_conns,
    timeout_default,
)

def _reconnect_shell_for_session(session_id, session_data, slog) -> bool:
    """
    After an interactive priv-esc hangs the PTY, open a fresh /bin/sh on the
    existing SSH connection (or rebuild SSH if the conn died).

    On success, rotates session logs into a new reconnect run folder.
    """
    slog.event(
        "RECONNECT_ATTEMPT",
        "Opening a fresh shell after breakage",
        server=session_data.get("server"),
        port=session_data.get("port"),
        username=session_data.get("username"),
        hostname=session_data.get("hostname"),
    )
    old = ssh_shells.get(session_id)
    if old is not None:
        try:
            old.close()
        except Exception as exc:  # noqa: BLE001
            slog.warning(f"old shell close: {exc}")

    ssh_conn = ssh_ssh_conns.get(session_id)
    try:
        def _new_ssh_conn():
            slog.info("Creating a new SSH connection")
            conn = ssh(
                user=session_data.get("username"),
                host=session_data.get("server"),
                port=int(session_data.get("port") or 22),
                password=session_data.get("password"),
                timeout=10,
                ignore_config=True,
            )
            conn.set_env("TERM", "")
            ssh_ssh_conns[session_id] = conn
            return conn

        if ssh_conn is None:
            ssh_conn = _new_ssh_conn()

        try:
            shell = _open_ssh_interactive_shell(ssh_conn)
        except Exception as shell_exc:  # noqa: BLE001
            # Cached connection may be dead after a hang — rebuild once.
            slog.warning(f"shell open on cached conn failed ({shell_exc}); rebuilding SSH")
            try:
                ssh_conn.close()
            except Exception:  # noqa: BLE001
                pass
            ssh_conn = _new_ssh_conn()
            shell = _open_ssh_interactive_shell(ssh_conn)

        drained = recv_for_duration(shell, 2)
        drain_text = drained.decode("utf-8", errors="replace") if drained else ""
        ssh_shells[session_id] = shell
        prompt_delimiters[session_id] = b"$ "
        # New conversation log for the post-reconnect life of the shell.
        new_slog = start_session_log_run(session_id, "reconnect")
        new_slog.event(
            "RECONNECT_OK",
            "Fresh /bin/sh ready — Full AI can continue",
            drain_preview=drain_text[:300],
            previous_run=slog.run_id,
        )
        log_ssh_lifecycle(
            "reconnect_ok",
            session_id,
            host=session_data.get("server"),
            port=session_data.get("port"),
        )
        return True
    except Exception as exc:  # noqa: BLE001
        slog.exception(f"RECONNECT_FAILED: {exc}")
        slog.event("RECONNECT_FAILED", str(exc))
        log_app(
            "ssh.reconnect_failed",
            level=logging.ERROR,
            session_id=session_id,
            error=str(exc),
        )
        ssh_shells.pop(session_id, None)
        return False


def recreate_shell(emit_func, session_id):
    message = "Exiting /bin/sh"
    log_app("ssh.recreate_shell", session_id=session_id)
    emit_func("message", {"data": message}, namespace="/get")
    ssh_conn = ssh_ssh_conns.get(session_id)
    if ssh_conn is None:
        ssh_conn = ssh(
            user=session.get('username'),
            host=session.get('server'),
            port=int(session.get('port') or 22),
            password=session.get('password'),
            timeout=10,
            ignore_config=True,
        )
        ssh_conn.set_env('TERM', '')
        ssh_ssh_conns[session_id] = ssh_conn
    shell = _open_ssh_interactive_shell(ssh_conn)
    ssh_shells[session_id] = shell
    # After you start a new shell, drain the buffer using the recv function \/
    shell_recvuntil_v2(
        shell, prompt_delimiter, drop=False, timeout=timeout_default, session=session
    )
    return jsonify(output='Started a new /bin/sh process'), 200
