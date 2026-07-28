"""SSH shell lifecycle: open, reuse, close, listener."""

from __future__ import annotations

from flask import session

from pwn import ssh
from ramigpt.utils import debug_logger, get_session_logger
from ramigpt.web.logging_config import log_ssh_lifecycle
from ramigpt.web.extensions import app, socketio
from ramigpt.web.shell.interaction import shell_interaction
from ramigpt.web.shell.recvuntil import shell_recvuntil
from ramigpt.web.state import (
    beroots,
    last_commands,
    linenums,
    linpeas_reports,
    loop,
    prompt_delimiter,
    prompt_delimiters,
    prompts,
    shell_listener_epoch,
    ssh_shells,
    ssh_ssh_conns,
    stop_full_ai_by_session,
    stop_task_flag,
    timeout_default,
    _prompt_history_stash,
)

def close_ssh_connection(session_id):
    # Invalidate any running shell_interaction for this session first.
    shell_listener_epoch[session_id] = shell_listener_epoch.get(session_id, 0) + 1
    shell = ssh_shells.pop(session_id, None)
    conn = ssh_ssh_conns.pop(session_id, None)
    priv = prompts.pop(session_id, None)
    if priv is not None and getattr(priv, "history", None):
        # Keep command history across disconnect so Full AI can avoid repeats
        # after reconnect (also reseeded from SHELL_IO logs as a fallback).
        _prompt_history_stash[session_id] = [
            {"command": e.get("command", ""), "output": e.get("output", "")}
            for e in priv.history
        ]
    prompt_delimiters.pop(session_id, None)
    last_commands.pop(session_id, None)
    beroots.pop(session_id, None)
    linenums.pop(session_id, None)
    linpeas_reports.pop(session_id, None)
    loop.pop(session_id, None)
    flag = stop_full_ai_by_session.pop(session_id, None)
    if flag:
        flag.set()
    try:
        if shell is not None:
            shell.close()
    except Exception as exc:  # noqa: BLE001
        debug_logger.debug(f"ssh.close shell error session_id={session_id!r}: {exc}")
    try:
        if conn is not None:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        debug_logger.debug(f"ssh.close conn error session_id={session_id!r}: {exc}")
    log_ssh_lifecycle("close", session_id, had_shell=shell is not None, had_conn=conn is not None)


def _open_ssh_interactive_shell(ssh_conn):
    """
    Open an interactive remote shell tube.

    pwntools ``ssh.process()`` needs a Python interpreter on the target. Some
    minimal lab images omit it, in which case ``process()`` returns None — fall
    back to ``ssh.system()`` / ``ssh.shell()`` which use a raw SSH channel.
    """
    if ssh_conn is None:
        raise RuntimeError("Cannot open shell: SSH connection is None")
    errors = []
    for label, opener in (
        ("process:/bin/sh", lambda: ssh_conn.process("/bin/sh", env={"TERM": ""})),
        ("process:/bin/bash", lambda: ssh_conn.process("/bin/bash", env={"TERM": ""})),
        # Login shell (no argv): required for rbash targets where absolute paths like
        # /bin/sh are rejected ("restricted: cannot specify `/' in command names").
        ("shell:login", lambda: ssh_conn.shell()),
        ("system:/bin/sh", lambda: ssh_conn.system("/bin/sh")),
        ("system:/bin/bash", lambda: ssh_conn.system("/bin/bash")),
        ("shell:/bin/bash", lambda: ssh_conn.shell("/bin/bash")),
        ("shell:/bin/sh", lambda: ssh_conn.shell("/bin/sh")),
    ):
        try:
            shell = opener()
            if shell is not None:
                debug_logger.debug(f"ssh.shell_opener ok label={label}")
                return shell
            errors.append(f"{label} returned None")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{label}: {exc}")
    raise RuntimeError(
        "Failed to open remote interactive shell "
        "(install python3 on the target for pwntools process()). "
        + "; ".join(errors[:6])
    )


def get_or_create_ssh_shell(session_id, create_new=False):
    existing = ssh_shells.get(session_id)
    if existing is not None:
        if create_new:
            close_ssh_connection(session_id)
        else:
            return existing
    if not create_new:
        raise RuntimeError(
            f"No SSH shell for session {session_id}; connect this session first"
        )

    ssh_conn = None
    shell = None
    try:
        # ignore_config: don't load ~/.ssh/known_hosts — lab/docker targets
        # regenerate host keys often (esp. host-network benchmarks on one IP).
        ssh_conn = ssh(
            user=session.get('username'),
            host=session.get('server'),
            port=session.get('port'),
            password=session.get('password'),
            timeout=10,
            ignore_config=True,
        )
        ssh_conn.set_env('TERM', '')

        shell = _open_ssh_interactive_shell(ssh_conn)
        shell_recvuntil(shell, prompt_delimiter, drop=False, timeout=timeout_default)

        ssh_shells[session_id] = shell
        ssh_ssh_conns[session_id] = ssh_conn
        log_ssh_lifecycle(
            "shell_open",
            session_id,
            host=session.get("server"),
            port=session.get("port"),
            user=session.get("username"),
            create_new=create_new,
        )
        return shell
    except Exception:
        debug_logger.exception(
            f"ssh.shell_open_failed session_id={session_id!r} "
            f"host={session.get('server')!r} port={session.get('port')}"
        )
        for obj in (shell, ssh_conn):
            try:
                if obj is not None:
                    obj.close()
            except Exception:  # noqa: BLE001
                pass
        ssh_shells.pop(session_id, None)
        ssh_ssh_conns.pop(session_id, None)
        raise


def start_shell_listener(session_id):
    """Background recv loop scoped to one inventory session (single active epoch)."""
    shell = ssh_shells.get(session_id)
    if shell is None:
        debug_logger.debug(f"ssh.listener_skip session_id={session_id!r} reason=no_shell")
        return
    # Bump epoch so any previous listener for this session exits quietly.
    shell_listener_epoch[session_id] = shell_listener_epoch.get(session_id, 0) + 1
    epoch = shell_listener_epoch[session_id]
    session_data = {
        "sid": session_id,
        "hostname": session.get("hostname"),
        "username": session.get("username"),
        "password": session.get("password"),
        "server": session.get("server"),
        "port": session.get("port"),
        "listener_epoch": epoch,
    }
    stop_task_flag.clear()

    def _emit(event, data, namespace="/get", **kwargs):
        payload = dict(data or {})
        payload["server_session_id"] = session_id
        room = kwargs.pop("to", None) or session_id
        socketio.emit(event, payload, namespace=namespace, to=room, **kwargs)

    log_ssh_lifecycle("listener_start", session_id, epoch=epoch)
    socketio.start_background_task(shell_interaction, shell, _emit, session_data)
