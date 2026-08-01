"""SSH connect, command execution, Full AI, and scanner tool routes."""

from __future__ import annotations

import threading
import time
import logging

from flask import Flask, jsonify, request, session

from ramigpt.ai import get_answer_with_usage
from ramigpt.config import get_settings
from ramigpt.domain import got_root
from ramigpt.session_v2 import resolve_ai_command
from ramigpt.utils import debug_logger, get_session_logger
from ramigpt.web.logging_config import log_app
from ramigpt.web import state
from ramigpt.web.ai.tasks import start_autonomous_task
from ramigpt.web.auth import login_required
from ramigpt.web.constants import TOOL_LABELS
from ramigpt.web.extensions import socketio
from ramigpt.web.prompt_helpers import _generate_ai_prompt, _make_priv_esc_prompt
from ramigpt.web.session_emit import emit_session, resolve_server_session_id
from ramigpt.web.shell.connection import get_or_create_ssh_shell
from ramigpt.web.shell.reconnect import recreate_shell
from ramigpt.web.shell.recv import recv_for_duration
from ramigpt.web.tools.scanners import execute_beroot, execute_linenum, execute_linpeas

TOOL_EXECUTORS = {
    "beroot": execute_beroot,
    "linenum": execute_linenum,
    "linpeas": execute_linpeas,
}

# Backward-compatible aliases for tests
_TOOL_EXECUTORS = TOOL_EXECUTORS
_TOOL_LABELS = TOOL_LABELS


def shell_conditions(command, shell, prompt_delimiter, session_data, just_got_root):
    """Legacy helper for special su/sudo command handling."""
    session_id = session_data.get("sid")
    priv_esc = state.prompts.get(session_id) if session_id else None
    if command.startswith("su "):
        while True:
            shell_output_bytes = recv_for_duration(shell, state.timeout_default)
            shell_output_lines = shell_output_bytes.decode("utf-8").split("\n")
            shell_output = shell_output_bytes.decode("utf-8").strip()
            if priv_esc is not None:
                priv_esc.add_history(
                    f"{prompt_delimiter.decode('utf-8').strip()} {command}",
                    shell_output,
                )
            if len(shell_output) <= 0:
                break
            last_line = shell_output_lines[-1]
            if got_root(session_data.get("hostname"), last_line):
                if session_id:
                    state.prompt_delimiters[session_id] = last_line
                socketio.emit("message", {"data": shell_output}, namespace="/get")
                socketio.emit("message", {"data": "pwned!", "color": "#ff0000"}, namespace="/get")
                just_got_root = True
                if priv_esc is not None:
                    summary = priv_esc.generate_summary()
                    socketio.emit(
                        "message",
                        {"data": f"{summary}\n", "color": "#1E90FF"},
                        namespace="/get",
                    )
                return
            if "Password:" in shell_output:
                debug_logger.info("password prompt detected (su)")
                shell.sendline(session_data.get("password"))
    if command.startswith("sudo ") and not command.startswith("sudo -l"):
        shell_output = recv_for_duration(shell, state.timeout_default).decode("utf-8").strip()
        if priv_esc is not None:
            priv_esc.add_history(
                f"{prompt_delimiter.decode('utf-8').strip()} {command}",
                shell_output,
            )
        if f"password for {session_data.get('username')}" in shell_output:
            debug_logger.info("password prompt detected (sudo)")
            shell.sendline(session_data.get("password"))

    if "sudo " in command and not command.startswith("sudo -l"):
        if priv_esc is not None:
            priv_esc.add_history(
                f"{prompt_delimiter.decode('utf-8').strip()} {command}",
                shell_output,
            )
        shell.sendline("!/bin/sh")
        if priv_esc is not None:
            priv_esc.add_history("!/bin/sh", shell_output)
        shell.sendline("id")
        if priv_esc is not None:
            priv_esc.add_history("id", shell_output)
        shell_output_bytes = recv_for_duration(shell, state.timeout_default)
        shell_output_lines = shell_output_bytes.decode("utf-8").split("\n")
        shell_output = shell_output_bytes.decode("utf-8").strip()
        for line in shell_output_lines:
            if got_root(session_data.get("hostname"), line):
                socketio.emit("message", {"data": shell_output}, namespace="/get")
                socketio.emit("message", {"data": "pwned!", "color": "#ff0000"}, namespace="/get")
                just_got_root = True
                if session_id:
                    state.prompt_delimiters[session_id] = shell_output_lines[-1]
                if priv_esc is not None:
                    summary = priv_esc.generate_summary()
                    socketio.emit(
                        "message",
                        {"data": f"{summary}\n", "color": "#1E90FF"},
                        namespace="/get",
                    )
                return
    return command, shell, prompt_delimiter, session_data, just_got_root


def register_ssh_routes(app: Flask) -> None:
    @app.route("/connect", methods=["POST"])
    def connect():
        try:
            credentials = request.get_json()
            username = credentials["username"]
            password = credentials["password"]
            server = credentials.get("server", "default_host")
            hostname = credentials.get("hostname", "pehost")
            port = int(credentials.get("port", 22))
            if request.path == "/connect":
                session["logged_in"] = True
                session["username"] = username
                session["password"] = password
                session["server"] = server
                session["port"] = port
                session["hostname"] = hostname
                session_id = session.sid
                try:
                    get_or_create_ssh_shell(session_id, create_new=True)
                    priv_esc_prompt = _make_priv_esc_prompt(
                        session_id, username, password, "Linux", "root"
                    )
                    state.prompts[session_id] = priv_esc_prompt
                    state.prompt_delimiters[session_id] = b"$ "
                    log_app(
                        "ssh.legacy_connect",
                        session_id=session_id,
                        host=server,
                        port=port,
                        user=username,
                    )
                    return jsonify(success=True)
                except Exception as e:
                    log_app(
                        "ssh.legacy_connect_failed",
                        level=logging.ERROR,
                        session_id=session_id,
                        error=str(e),
                    )
                    return jsonify(success=False, error=str(e)), 500
            return jsonify(success=False), 401
        except Exception as e:
            socketio.emit(
                "message",
                {"data": f"[ERROR] Failed to execute command - {e}"},
                namespace="/get",
            )
            debug_logger.exception("Failed to execute command.")
            return jsonify(error=str(e)), 500

    @app.route("/get", methods=["GET"])
    @login_required
    def test():
        time_str = time.strftime("%H:%M:%S")
        socketio.emit("message", {"data": "Current time: 44" + time_str}, namespace="/get")
        return jsonify(output="response"), 200

    @app.route("/action3", methods=["POST", "DELETE"])
    @login_required
    def action3():
        if not request.is_json:
            debug_logger.warning("Request does not contain JSON data.")
            return jsonify(error="Invalid request format."), 400

        action = (request.json.get("action") or "").strip()
        if not action:
            return jsonify(error="Missing action parameter."), 400

        time_str = time.strftime("%H:%M:%S")

        if action == "start":
            session_id = resolve_server_session_id()
            if not session_id or session_id not in state.ssh_shells:
                return jsonify(error="No active SSH connection. Connect this session first."), 400
            if session_id not in state.ssh_ssh_conns:
                return jsonify(error="No SSH connection object for this session."), 400
            raw_ai = request.json.get("ai", request.json.get("with_ai", True))
            if isinstance(raw_ai, str):
                with_ai = raw_ai.strip().lower() not in {"0", "false", "no", "off"}
            else:
                with_ai = bool(raw_ai)
            tool = (request.json.get("tool") or "beroot").strip().lower()
            if tool == "beroot" and request.json.get("tool") is None:
                legacy = (request.json.get("toolSelector") or "").strip()
                if legacy.lower() in {"linenum", "linenum.sh"}:
                    tool = "linenum"
                elif legacy.lower() in {"linpeas", "linpeas.sh"}:
                    tool = "linpeas"
                elif legacy.lower() in {"beroot", "beroot.py"}:
                    tool = "beroot"
            execute_fn = TOOL_EXECUTORS.get(tool)
            if execute_fn is None:
                return jsonify(
                    error=f"Unknown tool {tool!r}. Available: {', '.join(TOOL_EXECUTORS)}"
                ), 400
            tool_label = TOOL_LABELS.get(tool, tool)
            state.loop[session_id] = 1
            log_app(
                "tool.start",
                session_id=session_id,
                tool=tool,
                with_ai=with_ai,
            )
            session_data_copy = {
                "sid": session_id,
                "username": session.get("username"),
                "password": session.get("password"),
                "hostname": session.get("hostname"),
                "server": session.get("server"),
                "port": session.get("port"),
                "with_ai": with_ai,
            }
            socketio.start_background_task(execute_fn, session_data_copy)
            emit_session(
                session_id,
                f"[{tool_label}] Tool run requested — dispatching to remote host (AI={'on' if with_ai else 'off'})…",
                color="#58a6ff",
            )
            return jsonify(output=f"{tool}_started", tool=tool, session_id=session_id, ai=with_ai), 200

        if action == "stop":
            session_id = resolve_server_session_id()
            if session_id:
                flag = state.stop_full_ai_by_session.setdefault(session_id, threading.Event())
                flag.set()
                emit_session(session_id, "Stopping…", color="#8b949e")
            debug_logger.info(f"Action '{action}' triggered at {time_str}.")
            return jsonify(output="response"), 200

        debug_logger.warning(f"Invalid action received: {action}")
        return jsonify(error="Invalid action specified."), 400

    @app.route("/action1", methods=["POST", "DELETE"])
    @login_required
    def action1():
        debug_logger.debug("Received request at /action1 endpoint.")

        if not request.is_json:
            debug_logger.warning("Request does not contain JSON data.")
            return jsonify(error="Invalid request format."), 400

        action = request.json.get("action", "").strip()
        if not action:
            return jsonify(error="Missing action parameter."), 400

        time_str = time.strftime("%H:%M:%S")
        session_id = resolve_server_session_id()
        if not session_id or session_id not in state.ssh_shells:
            return jsonify(error="No active SSH connection. Connect this session first."), 400

        session["active_server_session_id"] = session_id
        session_data = {
            "sid": session_id,
            "username": session.get("username"),
            "password": session.get("password"),
            "hostname": session.get("hostname"),
            "server": session.get("server"),
            "port": session.get("port"),
        }

        if action == "start":
            flag = state.stop_full_ai_by_session.setdefault(session_id, threading.Event())
            flag.clear()
            state.root_won_by_session[session_id] = False
            state.loop[session_id] = 1
            get_session_logger(session_id).event(
                "FULL_AI_REQUESTED",
                "Full AI start requested from UI",
                hostname=session_data.get("hostname"),
                server=session_data.get("server"),
                port=session_data.get("port"),
                provider=get_settings().ai_provider,
                model=get_settings().active_model(),
            )
            start_autonomous_task(session_data)
        elif action == "stop":
            flag = state.stop_full_ai_by_session.setdefault(session_id, threading.Event())
            flag.set()
            debug_logger.info(
                f"Action '{action}' triggered at {time_str}. Emitting 'Stopping..' message."
            )
            get_session_logger(session_id).event("FULL_AI_STOP_REQUESTED", "Stop Full AI requested from UI")
            emit_session(session_id, "Stopping Full AI…", color="#8b949e")
        else:
            debug_logger.warning(f"Invalid action received: {action}")
            return jsonify(error="Invalid action specified."), 400

        return jsonify(output="response"), 200

    @app.route("/execute", methods=["POST"])
    @login_required
    def execute():
        state.stop_task_flag.clear()

        session_id = resolve_server_session_id()
        if not session_id or session_id not in state.ssh_shells:
            debug_logger.warning("execute rejected: no active SSH session")
            return jsonify(error="No active SSH connection. Connect this session first."), 400

        session["active_server_session_id"] = session_id
        slog = get_session_logger(session_id)
        try:
            prompt_delimiter = state.prompt_delimiters.get(session_id, "$")
            shell = state.ssh_shells.get(session_id)
            priv_esc = state.prompts.get(session_id)

            command = request.json.get("command", "")
            from_ai = len(command) < 1
            if command == "exit":
                slog.event("SHELL_EXIT", "User requested exit — recreating /bin/sh")
                return recreate_shell(socketio.emit, session_id)

            if from_ai:
                from ramigpt.ai.refusal import detect_policy_violation

                prompt = _generate_ai_prompt(priv_esc)
                system = (
                    "You help complete authorized, owner-operated Linux lab / CTF "
                    "exercises. Reply with a single non-interactive shell command only."
                )
                response, usage = get_answer_with_usage(system, prompt)
                command = resolve_ai_command(response, priv_esc)
                slog.ai_turn(
                    request_n=len(getattr(priv_esc, "history", []) or []) + 1,
                    system=system,
                    prompt=prompt or "",
                    raw_response=response or "",
                    filtered_command=command or "",
                    source="execute_ai",
                    provider=get_settings().ai_provider,
                    model=get_settings().active_model(),
                    usage=usage,
                )
                if not command:
                    policy_reason = detect_policy_violation(response or "")
                    msg = (
                        policy_reason
                        or "AI returned no usable command"
                    ) + " — nothing sent to the target."
                    emit_session(session_id, f"[AI] {msg}", color="#f85149")
                    return jsonify(error=msg, policy_block=bool(policy_reason)), 400
            else:
                slog.info(f"manual command requested: {command}")

            state.last_commands[session_id] = command
            shell.sendline(command)
            delim = (
                prompt_delimiter.decode("utf-8").strip()
                if isinstance(prompt_delimiter, (bytes, bytearray))
                else str(prompt_delimiter).strip()
            )
            emit_session(session_id, f"{delim} {command}")
            slog.info(f"sent to shell ({'ai' if from_ai else 'manual'}): {delim} {command}")
            return jsonify(output=""), 200
        except Exception as e:
            sid = resolve_server_session_id()
            if sid:
                emit_session(sid, f"[ERROR] Failed to execute command - {e}", color="#f85149")
                get_session_logger(sid).exception(f"Failed to execute command: {e}")
            debug_logger.exception(f"execute failed session_id={session_id!r}")
            return jsonify(error=str(e)), 500
