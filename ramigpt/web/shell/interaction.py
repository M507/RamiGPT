"""Background listener for manual terminal I/O."""

from __future__ import annotations

from ramigpt.domain.root_detection import diagnose_root
from ramigpt.utils import debug_logger, get_session_logger
from ramigpt.web.extensions import app, socketio
from ramigpt.web.shell.password import _answer_password_prompt, _looks_like_password_prompt, _still_waiting_on_password
from ramigpt.web.state import (
    last_commands,
    loop,
    prompts,
    shell_listener_epoch,
    ssh_shells,
)

def shell_interaction(shell, emit_func, session, max_retries=1000000):
    """
    One recv loop per session epoch. Survives shell replacement without
    broadcasting fake UI disconnects; exits when the session is closed or
    superseded by a newer listener.
    """
    with app.app_context():
        session_id = session['sid']
        epoch = session.get("listener_epoch")
        slog = get_session_logger(session_id)
        priv_esc = prompts.get(session_id)
        if epoch is not None and shell_listener_epoch.get(session_id) == epoch:
            slog.info(f"shell_interaction listener started (epoch={epoch})")
        io_n = 0
        idle_closed = 0

        while True:
            if epoch is not None and shell_listener_epoch.get(session_id) != epoch:
                slog.info(f"shell_interaction listener exiting (stale epoch={epoch})")
                return
            try:
                while True:
                    if epoch is not None and shell_listener_epoch.get(session_id) != epoch:
                        return
                    socketio.sleep(0.2)
                    if loop.get(session_id):
                        socketio.sleep(0.3)
                        continue
                    shell = ssh_shells.get(session_id)
                    if shell is None:
                        idle_closed += 1
                        if idle_closed > 25:
                            slog.info("shell_interaction: no shell — exiting")
                            return
                        socketio.sleep(0.2)
                        continue
                    idle_closed = 0
                    try:
                        data = shell.recv(timeout=1)
                    except EOFError:
                        if epoch is not None and shell_listener_epoch.get(session_id) != epoch:
                            return
                        if session_id in ssh_shells and ssh_shells.get(session_id) is not shell:
                            slog.debug("shell_interaction: shell replaced — switching")
                            continue
                        if session_id not in ssh_shells:
                            slog.info("shell_interaction: shell closed — exiting")
                            return
                        socketio.sleep(0.2)
                        continue
                    if not data:
                        continue

                    priv_esc = prompts.get(session_id)
                    decoded_data = data.decode("utf-8", errors="replace").strip()
                    command = last_commands.get(session_id, "")

                    if _looks_like_password_prompt(decoded_data) and _still_waiting_on_password(decoded_data):
                        slog.event(
                            "PASSWORD_PROMPT",
                            "shell_interaction answered a password prompt",
                            command=command,
                        )
                        after = _answer_password_prompt(shell, session, slog)
                        decoded_data = (decoded_data + "\n" + (after or "")).strip()
                        emit_func(
                            "message",
                            {"data": f"{decoded_data}\n", "color": "#f0b429"},
                            namespace="/get",
                        )
                        io_n += 1
                        slog.shell_io(
                            request_n=io_n,
                            command=command or "(password prompt)",
                            output=decoded_data,
                            note="auto password answer",
                            source="manual",
                        )
                        if priv_esc is not None:
                            priv_esc.add_history(
                                command or "(password prompt)",
                                priv_esc.process_command_output(command, decoded_data),
                            )
                        continue

                    if priv_esc is not None:
                        decoded_data = priv_esc.process_command_output(command, decoded_data)
                        priv_esc.add_history(command, decoded_data)
                    io_n += 1
                    slog.shell_io(
                        request_n=io_n,
                        command=command or "",
                        output=decoded_data or "",
                        note="shell_interaction listener",
                        source="manual",
                    )
                    hostname = session.get("hostname")
                    diagnosis = diagnose_root(hostname, decoded_data)
                    if diagnosis.get("got_root") or ("uid=0" in (decoded_data or "")):
                        slog.root_check(
                            request_n=io_n,
                            hostname=hostname or "",
                            last_line=(decoded_data.split("\n")[-1] if decoded_data else ""),
                            shell_output=decoded_data or "",
                            won=bool(diagnosis.get("got_root")),
                            reasons=diagnosis,
                        )

                    emit_func("message", {"data": f"{decoded_data}\n"}, namespace="/get")

            except EOFError:
                if epoch is not None and shell_listener_epoch.get(session_id) != epoch:
                    return
                if session_id in ssh_shells:
                    debug_logger.debug(f"shell_interaction EOF (recoverable) session_id={session_id!r}")
                    socketio.sleep(0.3)
                    continue
                slog.info("shell_interaction EOF — session shell gone")
                return
            except Exception:
                if epoch is not None and shell_listener_epoch.get(session_id) != epoch:
                    return
                socketio.sleep(0.3)
                continue
