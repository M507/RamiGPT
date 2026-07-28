"""Full AI autonomous privilege-escalation loop."""

from __future__ import annotations

import threading
import time

from flask import session as flask_session

from ramigpt.ai import get_answer_with_usage
from ramigpt.config import get_settings
from ramigpt.domain.root_detection import diagnose_root
from ramigpt.session_v2 import execute_command as session_v2_execute_command, is_enabled as session_v2_enabled, resolve_ai_command
from ramigpt.utils import GlobalTimer, debug_logger, get_session_logger
from ramigpt.web.ai.timing import _ai_sleep, _wait_or_stop
from ramigpt.web.extensions import app, socketio
from ramigpt.web.prompt_helpers import _debug_enabled, _generate_ai_prompt, _max_ai_requests, _seed_prompt_history
from ramigpt.web.session_emit import emit_session
from ramigpt.web.shell.reconnect import _reconnect_shell_for_session
from ramigpt.web.shell.password import _answer_password_prompt, _looks_like_password_prompt, _still_waiting_on_password
from ramigpt.web.shell.prompt_detect import _is_shell_prompt_line, _looks_like_editor_stuck, _try_quit_editor
from ramigpt.web.shell.recv import _interrupt_shell, _safe_decode, recv_for_duration
from ramigpt.web.shell.recvuntil import _session_v2_bridge, shell_recvuntil_v4
from ramigpt.web.state import (
    loop,
    prompt_delimiters,
    prompts,
    root_won_by_session,
    ssh_shells,
    stop_full_ai_by_session,
    stop_task_flag,
)

def autonomous(session_data):
    global stop_task_flag

    with app.app_context():
        """Background task for a specific session using passed session data."""
        session_id = session_data['sid']
        slog = get_session_logger(session_id)
        ai_settings = get_settings()
        max_reqs = _max_ai_requests()
        emit_session(session_id, f'Giving AI full freedom to send {max_reqs} commands', color="#58a6ff")
        debug_logger.info(
            f"full_ai.start session_id={session_id!r} host={session_data.get('server')!r}:"
            f"{session_data.get('port')}"
        )
        slog.event(
            "FULL_AI_START",
            f"Starting autonomous loop (max_reqs={max_reqs})",
            hostname=session_data.get("hostname"),
            server=session_data.get("server"),
            port=session_data.get("port"),
            provider=ai_settings.ai_provider,
            model=ai_settings.active_model(),
        )
        GlobalTimer.start(
            session_id,
            hostname=session_data.get("hostname"),
            server=session_data.get("server"),
            port=session_data.get("port"),
            username=session_data.get("username"),
            max_reqs=max_reqs,
        )
        i = 0
        just_got_root = False
        stop_reason = "max_requests"
        stop_flag = stop_full_ai_by_session.setdefault(session_id, threading.Event())
        reconnect_budget = 3
        consecutive_empty_ai = 0
        max_consecutive_empty_ai = 3
        # Safely fetching session-specific data with default values and debugging
        prompt_delimiter = prompt_delimiters.get(session_id, "$")  # Default to "#" if not set
        shell = ssh_shells.get(session_id)
        priv_esc = prompts.get(session_id)
        if priv_esc is not None:
            # Pull any commands from earlier Full AI / manual runs (e.g. stopped
            # before add_history) so a restarted Full AI does not repeat them.
            seeded = _seed_prompt_history(session_id, priv_esc)
            if seeded:
                slog.info(f"reseeded {seeded} history entr(y/ies) from stash/logs")

        slog.info(f"initial shell={bool(shell)} prompt_delimiter={prompt_delimiter!r} priv_esc={bool(priv_esc)}")
        
        while i < max_reqs:  # Ensure the loop runs only if it's enabled
            # Interruptible delay: Stop during this wait must not start the next LLM call
            # (previously checked only *before* a blind sleep — race in session 002_…64518Z).
            if _wait_or_stop(stop_flag, 1):
                stop_reason = "stopped"
                slog.event("FULL_AI_STOP", "Stop flag set — exiting autonomous loop")
                break
            i += 1
            try:
                emit_session(session_id, f"AI request#{i}======================================================================", color="#f85149")
                slog.info(f"AI request#{i}")
                
                # Create a prompt
                prompt = _generate_ai_prompt(priv_esc)
                if stop_flag.is_set():
                    stop_reason = "stopped"
                    slog.event("FULL_AI_STOP", "Stop before AI request — exiting")
                    break
                if _debug_enabled():
                    emit_session(
                        session_id,
                        f"[DEBUG] About to send prompt:\n{prompt}",
                        color="#d2a8ff",
                    )
                
                # Prompt/response live in the session run log only (not debug.log).
                slog.debug(f"prompt #{i}:\n{prompt}")

                system = "You are an experienced pentester."
                ai_started = time.monotonic()
                response, usage = get_answer_with_usage(system, prompt)
                ai_duration = round(time.monotonic() - ai_started, 3)
                if stop_flag.is_set():
                    # LLM call already in flight isn't cancelled; discard the result.
                    stop_reason = "stopped"
                    slog.event(
                        "FULL_AI_STOP",
                        "Stop after AI response — discarding command, exiting",
                    )
                    break
                trimmed_ai_command = resolve_ai_command(response, priv_esc)
                command = trimmed_ai_command
                use_session_v2 = session_v2_enabled()
                settings = get_settings()
                slog.ai_turn(
                    request_n=i,
                    system=system,
                    prompt=prompt or "",
                    raw_response=response or "",
                    filtered_command=command or "",
                    provider=settings.ai_provider,
                    model=settings.active_model(),
                    usage=usage,
                    duration_seconds=ai_duration,
                )
                if not command:
                    if not (response or "").strip():
                        consecutive_empty_ai += 1
                    slog.warning(
                        f"AI returned empty/unusable command on request#{i}; skipping "
                        f"(consecutive_empty={consecutive_empty_ai})"
                    )
                    if consecutive_empty_ai >= max_consecutive_empty_ai:
                        stop_reason = "ai_empty_response"
                        settings = get_settings()
                        msg = (
                            f"AI returned no usable output {consecutive_empty_ai} times in a row "
                            f"({settings.ai_provider}/{settings.active_model()}). "
                            "Some Open WebUI models respond with null on security prompts — "
                            "switch models in Settings or check Open WebUI logs."
                        )
                        slog.error(msg)
                        emit_session(session_id, f"[Full AI] {msg}", color="#f85149")
                        break
                    continue
                consecutive_empty_ai = 0
                shell = ssh_shells.get(session_id) or shell
                if shell is None:
                    slog.error("No shell available before sendline — attempting reconnect")
                    if not _reconnect_shell_for_session(session_id, session_data, slog):
                        stop_reason = "reconnect_failed"
                        break
                    slog = get_session_logger(session_id)
                    shell = ssh_shells.get(session_id)
                delim = prompt_delimiter.decode('utf-8').strip() if isinstance(prompt_delimiter, (bytes, bytearray)) else str(prompt_delimiter).strip()
                shell_exec_started = time.monotonic()
                if use_session_v2:
                    slog.info("session_v2: interactive driver active")
                else:
                    shell.sendline(command)
                emit_session(session_id, f"{delim} {command}")
                slog.info(f"sent to shell: {delim} {command}")
                # Record immediately so a Stop / timeout still leaves the command
                # in history for the next Full AI run ("Do not repeat…").
                priv_esc.add_history(command, "")

                shell_output_bytes = None
                shell_output_lines = []
                shell_output_lines_string = None
                shell_output = None
                last_line = ""

                if not just_got_root:
                    if use_session_v2:
                        run = session_v2_execute_command(
                            shell,
                            command,
                            bridge=_session_v2_bridge(),
                            hostname=session_data.get("hostname") or "",
                            password=session_data.get("password") or "",
                            timeout=12.0,
                        )
                        if run.notes:
                            slog.info(f"session_v2 notes: {', '.join(run.notes)}")
                        shell_output = run.shell_output
                        shell_output_lines = run.shell_output_lines
                        last_line = run.last_line or (
                            shell_output_lines[-1] if shell_output_lines else ""
                        )
                        if shell_output is None:
                            slog.shell_io(
                                request_n=i,
                                command=command,
                                output="(None — session v2 returned no output)",
                                note="session_v2_empty_output",
                                duration_seconds=round(time.monotonic() - shell_exec_started, 3),
                            )
                        else:
                            slog.shell_io(
                                request_n=i,
                                command=command,
                                output=shell_output,
                                duration_seconds=round(time.monotonic() - shell_exec_started, 3),
                            )

                        if run.got_root:
                            slog.root_check(
                                request_n=i,
                                hostname=session_data.get("hostname") or "",
                                last_line=last_line or "",
                                shell_output=shell_output or "",
                                won=True,
                                reasons=diagnose_root(
                                    session_data.get("hostname"), shell_output or last_line
                                ),
                            )
                            if shell_output:
                                emit_session(session_id, shell_output)
                            emit_session(session_id, "pwned!", color="#ff0000")
                            just_got_root = True
                            stop_reason = "root"
                            root_won_by_session[session_id] = True
                            try:
                                from ramigpt.benchmark.orchestrator import mark_root_won
                                mark_root_won(session_id)
                            except Exception:
                                pass
                            if last_line.endswith("#") or last_line == "#":
                                prompt_delimiters[session_id] = b"# "
                                prompt_delimiter = b"# "
                            priv_esc.add_history(command, shell_output or "")
                            summary = priv_esc.generate_summary()
                            slog.block("SUMMARY", summary or "")
                            emit_session(session_id, f"{summary}\n", color="#1E90FF")
                            break

                        if run.needs_reconnect:
                            if stop_flag.is_set():
                                stop_reason = "stopped"
                                priv_esc.add_history(
                                    command,
                                    (shell_output or "")
                                    + "\n[runner] command stopped / timed out",
                                )
                                slog.event("FULL_AI_STOP", "Stop during session v2 recovery — exiting")
                                break
                            dump_path = slog.breakage(
                                "prompt_timeout_after_command",
                                command=command,
                                shell_output=shell_output,
                                needs_reconnect=True,
                                ai_request=i,
                                hint="session_v2 could not restore prompt; reconnecting",
                            )
                            debug_logger.warning(
                                f"[BREAKAGE] session={session_id} session_v2 needs reconnect command={command!r} dump={dump_path}"
                            )
                            emit_session(
                                session_id,
                                "[BREAKAGE] Shell desynced — reconnecting…",
                                color="#f85149",
                            )
                            priv_esc.add_history(
                                command,
                                (shell_output or "") + "\n[runner] command hung / lost shell prompt",
                            )
                            if reconnect_budget > 0 and _reconnect_shell_for_session(session_id, session_data, slog):
                                reconnect_budget -= 1
                                slog = get_session_logger(session_id)
                                shell = ssh_shells.get(session_id)
                                prompt_delimiter = prompt_delimiters.get(session_id, prompt_delimiter)
                                emit_session(
                                    session_id,
                                    f"[RECONNECT] Shell restored ({reconnect_budget} reconnect(s) left). Continuing Full AI…",
                                    color="#58a6ff",
                                )
                                continue
                            slog.event(
                                "RECONNECT_EXHAUSTED",
                                "Could not restore shell — stopping Full AI for this session",
                                reconnect_budget=reconnect_budget,
                            )
                            emit_session(session_id, "[BREAKAGE] Reconnect failed — stopping Full AI", color="#f85149")
                            stop_reason = "reconnect_exhausted"
                            break
                    else:
                        shell_output_bytes, \
                        shell_output_lines, \
                        shell_output_lines_string, \
                        shell_output = shell_recvuntil_v4(shell, prompt_delimiter, drop=False, timeout=8, session=session_data, emit_func=socketio.emit)

                        if shell_output is None:
                            slog.shell_io(
                                request_n=i,
                                command=command,
                                output="(None — recv timed out / no prompt delimiter)",
                                note="shell_recvuntil_v4 returned None",
                                duration_seconds=round(time.monotonic() - shell_exec_started, 3),
                            )
                        else:
                            slog.shell_io(
                                request_n=i,
                                command=command,
                                output=shell_output,
                                duration_seconds=round(time.monotonic() - shell_exec_started, 3),
                            )
                    
                    # If it hangs (common after interactive priv-esc like vim/awk shells)
                    if not use_session_v2 and shell_output == None:
                        if stop_flag.is_set():
                            stop_reason = "stopped"
                            priv_esc.add_history(
                                command,
                                "[runner] command stopped / timed out",
                            )
                            slog.event("FULL_AI_STOP", "Stop during command wait — exiting")
                            break
                        slog.warning(f"recv timeout after command: {command!r}")
                        # Stop runaway commands (grep -r / find / …) before draining.
                        _interrupt_shell(shell)
                        _ai_sleep(0.2)
                        _interrupt_shell(shell)
                        shell_output_bytes = recv_for_duration(shell, 2)
                        shell_output = _safe_decode(shell_output_bytes).strip()
                        shell_output_lines = shell_output.split("\n")
                        if shell_output:
                            emit_session(session_id, shell_output)
                        slog.block(
                            f"HANG_RECOVERY_DRAIN #{i}",
                            f"after timeout drain:\n{shell_output}",
                        )

                        # Interactive `sudo vim /path` leaves the PTY in vim; Ctrl-C
                        # alone often prints "Type :qa …". Quit the editor before
                        # treating this as a hard reconnect (session 003_…195756Z).
                        if _looks_like_editor_stuck(shell_output):
                            slog.event(
                                "EDITOR_STUCK",
                                "Detected interactive editor — sending :qa!",
                                command=command,
                                ai_request=i,
                            )
                            quit_drain = _try_quit_editor(shell)
                            if quit_drain:
                                emit_session(session_id, quit_drain)
                                shell_output = (shell_output + "\n" + quit_drain).strip()
                                shell_output_lines = shell_output.split("\n")
                                slog.block(
                                    f"EDITOR_QUIT_DRAIN #{i}",
                                    f"after :qa!:\n{quit_drain}",
                                )
                            last_after_quit = (
                                shell_output_lines[-1] if shell_output_lines else ""
                            ).strip()
                            if _is_shell_prompt_line(last_after_quit):
                                slog.info("hang recovery: prompt restored after editor quit")

                        hostname = session_data.get('hostname')
                        hang_diag = diagnose_root(hostname, shell_output)
                        if not hang_diag.get("got_root") and shell_output_lines:
                            for ln in shell_output_lines:
                                dln = diagnose_root(hostname, ln)
                                if dln.get("got_root"):
                                    hang_diag = dln
                                    break
                        # Nested root shells often show only `#` — that IS success.
                        if hang_diag.get("got_root"):
                            slog.root_check(
                                request_n=i,
                                hostname=hostname or "",
                                last_line=(shell_output_lines[-1] if shell_output_lines else "") or "",
                                shell_output=shell_output or "",
                                won=True,
                                reasons=hang_diag,
                            )
                            if shell_output:
                                emit_session(session_id, shell_output)
                            emit_session(session_id, "pwned!", color="#ff0000")
                            just_got_root = True
                            stop_reason = "root"
                            root_won_by_session[session_id] = True
                            try:
                                from ramigpt.benchmark.orchestrator import mark_root_won
                                mark_root_won(session_id)
                            except Exception:
                                pass
                            last = (shell_output_lines[-1] if shell_output_lines else "").strip()
                            if last.endswith("#") or last == "#":
                                prompt_delimiters[session_id] = b"# "
                                prompt_delimiter = b"# "
                            priv_esc.add_history(command, shell_output or "")
                            summary = priv_esc.generate_summary()
                            slog.block("SUMMARY", summary or "")
                            emit_session(session_id, f"{summary}\n", color="#1E90FF")
                            break

                        # Prefer answering sudo/su password prompts over hang-reconnect.
                        if _looks_like_password_prompt(shell_output) and _still_waiting_on_password(shell_output):
                            slog.event(
                                "PASSWORD_PROMPT",
                                "Timeout was a password prompt — supplying session password",
                                command=command,
                                ai_request=i,
                            )
                            after_pw = _answer_password_prompt(shell, session_data, slog)
                            # Continue reading until the normal shell prompt returns.
                            more_bytes, more_lines, _, more_out = shell_recvuntil_v4(
                                shell,
                                prompt_delimiter,
                                drop=False,
                                timeout=8,
                                session=session_data,
                                emit_func=socketio.emit,
                            )
                            if more_out is None:
                                extra = recv_for_duration(shell, 3)
                                more_out = (after_pw or "") + "\n" + _safe_decode(extra)
                                more_lines = more_out.split("\n")
                            else:
                                more_out = ((after_pw or "") + "\n" + more_out).strip()
                                more_lines = more_out.split("\n")
                            shell_output = more_out.strip()
                            shell_output_lines = more_lines
                            slog.shell_io(
                                request_n=i,
                                command=command,
                                output=shell_output,
                                note="after password prompt answered",
                            )
                            # Fall through to normal history / root check below.
                        else:
                            last_drain = (shell_output_lines[-1] if shell_output_lines else "").strip()
                            # If we already have a healthy prompt back after Ctrl-C, continue.
                            if _is_shell_prompt_line(last_drain):
                                slog.info("hang recovery: prompt restored after interrupt")
                                # Fall through to normal history / root check.
                            elif stop_flag.is_set():
                                stop_reason = "stopped"
                                priv_esc.add_history(
                                    command,
                                    (shell_output or "")
                                    + "\n[runner] command stopped / timed out",
                                )
                                slog.event("FULL_AI_STOP", "Stop during hang recovery — exiting")
                                break
                            else:
                                # Desynced or nested UI — open a clean /bin/sh and continue.
                                dump_path = slog.breakage(
                                    "prompt_timeout_after_command",
                                    command=command,
                                    shell_output=shell_output,
                                    needs_reconnect=True,
                                    ai_request=i,
                                    hint="No stable prompt after interrupt; reconnecting",
                                )
                                debug_logger.warning(
                                    f"[BREAKAGE] session={session_id} needs reconnect after command={command!r} dump={dump_path}"
                                )
                                emit_session(
                                    session_id,
                                    "[BREAKAGE] Shell desynced — reconnecting…",
                                    color="#f85149",
                                )
                                priv_esc.add_history(
                                    command,
                                    (shell_output or "") + "\n[runner] command hung / lost shell prompt",
                                )
                                if reconnect_budget > 0 and _reconnect_shell_for_session(session_id, session_data, slog):
                                    reconnect_budget -= 1
                                    slog = get_session_logger(session_id)
                                    shell = ssh_shells.get(session_id)
                                    prompt_delimiter = prompt_delimiters.get(session_id, prompt_delimiter)
                                    emit_session(
                                        session_id,
                                        f"[RECONNECT] Shell restored ({reconnect_budget} reconnect(s) left). Continuing Full AI…",
                                        color="#58a6ff",
                                    )
                                    continue
                                slog.event(
                                    "RECONNECT_EXHAUSTED",
                                    "Could not restore shell — stopping Full AI for this session",
                                    reconnect_budget=reconnect_budget,
                                )
                                emit_session(session_id, "[BREAKAGE] Reconnect failed — stopping Full AI", color="#f85149")
                                stop_reason = "reconnect_exhausted"
                                break

                    last_line = shell_output_lines[-1] if shell_output_lines else ""
                
                processed_output = priv_esc.remove_last_line(shell_output)
                processed_output = priv_esc.process_command_output(command, processed_output)
                # Do not prefix with the shell prompt — that taught the model to emit "$ cmd".
                priv_esc.add_history(command, processed_output)
                slog.block(
                    f"HISTORY_APPEND #{i}",
                    f"history_command: {command}\n\nprocessed_output:\n{processed_output}",
                )
                hostname = session_data.get('hostname')
                # Prefer last line (real prompt / id). Never score every dump line —
                # a lone `#` comment mid-/etc would false-trigger root.
                diagnosis = diagnose_root(hostname, last_line)
                if not diagnosis.get("got_root"):
                    # Full blob only for uid=0(root) / root@host# markers, not comment lines.
                    diagnosis = diagnose_root(hostname, shell_output)
                if not diagnosis.get("got_root") and shell_output_lines:
                    for ln in shell_output_lines[-5:]:
                        if "uid=0" in ln or "euid=0" in ln or (
                            ln.strip().startswith("root@") and "#" in ln
                        ):
                            dln = diagnose_root(hostname, ln)
                            if dln.get("got_root"):
                                diagnosis = dln
                                break
                won = bool(diagnosis.get("got_root"))
                slog.root_check(
                    request_n=i,
                    hostname=hostname or "",
                    last_line=last_line or "",
                    shell_output=shell_output or "",
                    won=won,
                    reasons=diagnosis,
                )

                if won:
                    if shell_output:
                        emit_session(session_id, shell_output)
                    emit_session(session_id, "pwned!", color="#ff0000")
                    just_got_root = True
                    stop_reason = "root"
                    root_won_by_session[session_id] = True
                    try:
                        from ramigpt.benchmark.orchestrator import mark_root_won
                        mark_root_won(session_id)
                    except Exception:
                        pass
                    summary = priv_esc.generate_summary()
                    slog.block("SUMMARY", summary or "")
                    emit_session(session_id, f"{summary}\n", color="#1E90FF")
                    break
            except Exception as e:
                err_l = str(e).lower()
                is_ai_provider_error = (
                    any(
                        token in err_l
                        for token in (
                            "ai provider",
                            "unreachable",
                            "connecttimeout",
                            "connection error",
                            "apitimeouterror",
                            "apiconnectionerror",
                            "timed out",
                            "model not found",
                            "empty http body",
                            "empty message",
                            "no choices",
                        )
                    )
                    and "recv" not in err_l
                )

                # Keep debug.log readable for expected provider outages (no full httpx stack).
                if is_ai_provider_error:
                    debug_logger.error(
                        f"full_ai.ai_provider_error session_id={session_id!r}: {e}"
                    )
                else:
                    debug_logger.exception(f"full_ai.error session_id={session_id!r}")
                slog.exception(f"Failed to execute command: {e}")
                slog.event("ERROR", str(e), ai_request=i)
                emit_session(session_id, f"Error: {str(e)}", color="#f85149")

                # Provider/network failures are not PTY faults — abort instead of
                # burning reconnect budget on pointless SSH respawns.
                if is_ai_provider_error:
                    stop_reason = "ai_provider_error"
                    break

                # Recover the PTY and continue Full AI instead of aborting on decode / tube faults.
                try:
                    _interrupt_shell(ssh_shells.get(session_id) or shell)
                except Exception:  # noqa: BLE001
                    pass
                if reconnect_budget > 0 and _reconnect_shell_for_session(session_id, session_data, slog):
                    reconnect_budget -= 1
                    slog = get_session_logger(session_id)
                    shell = ssh_shells.get(session_id)
                    prompt_delimiter = prompt_delimiters.get(session_id, prompt_delimiter)
                    emit_session(
                        session_id,
                        f"[RECONNECT] Recovered after error ({reconnect_budget} left). Continuing…",
                        color="#58a6ff",
                    )
                    continue
                stop_reason = "error"
                break
        slog.event(
            "FULL_AI_END",
            "Autonomous loop finished",
            got_root=just_got_root,
            requests_run=i,
            stop_reason=stop_reason,
            provider=get_settings().ai_provider,
            model=get_settings().active_model(),
        )
        GlobalTimer.stop(
            session_id,
            label="FULL_AI",
            outcome="root" if just_got_root else stop_reason,
            requests_run=i,
            got_root=just_got_root,
        )
        debug_logger.info(
            f"full_ai.end session_id={session_id!r} got_root={just_got_root} "
            f"requests={i} reason={stop_reason}"
        )
        # Re-enable interactive shell listener (paused while Full AI owns the PTY).
        loop[session_id] = 0
        emit_session(
            session_id,
            f"[Full AI] finished (reason={stop_reason})",
            color="#8b949e",
        )
        try:
            from ramigpt.benchmark.orchestrator import mark_full_ai_finished
            mark_full_ai_finished(
                session_id,
                requests_run=i,
                got_root=just_got_root,
                provider=get_settings().ai_provider,
                model=get_settings().active_model(),
                stop_reason=stop_reason,
            )
        except Exception:
            pass
