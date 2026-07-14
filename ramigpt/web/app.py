from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
from flask_socketio import SocketIO, emit, join_room, leave_room
from functools import wraps
from pathlib import Path
import logging
import os
import time
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("PWNLIB_NOTERM", "1")
logging.getLogger("pwnlib").setLevel(logging.ERROR)

import threading
# Shared variable accessible to the background task and main application
stop_task_flag = threading.Event()
stop_full_ai = threading.Event()
# Per inventory-session stop flags for Full AI
stop_full_ai_by_session = {}

from pwn import *
context.log_level = "error"
from ramigpt.ai import get_answer
from ramigpt.ai.factory import create_provider
from ramigpt.domain import PrivEscPrompt, got_root, normalize_ai_command
from ramigpt.domain.root_detection import diagnose_root
from ramigpt.utils import (
    remove_matching_quotes,
    read_file_to_string,
    debug_logger,
    GlobalTimer,
    get_session_logger,
    start_session_log_run,
)
from ramigpt.config import get_settings, get_settings_manager
from ramigpt.paths import (
    BEROOT_DIR,
    BEROOT_DOWNLOADS_DIR,
    CERTS_DIR,
    SESSIONS_DIR,
    STATIC_DIR,
    TEMPLATES_DIR,
    ensure_runtime_dirs,
)

ensure_runtime_dirs()


def _looks_like_password_prompt(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return (
        "[sudo] password for" in lower
        or "password for" in lower
        or lower.rstrip().endswith("password:")
        or "\npassword:" in lower
        or lower.strip() == "password:"
    )


def _answer_password_prompt(shell, session_data, slog=None) -> str:
    """Send the session password once and drain leftover prompt noise."""
    password = session_data.get("password") or ""
    if slog is not None:
        slog.info("answering password prompt (password not logged)")
    shell.sendline(password)
    drained = recv_for_duration(shell, 2)
    return drained.decode("utf-8", errors="replace") if drained else ""

# Endpoints reachable without an active SSH session (workspace is open by default).
PUBLIC_ENDPOINTS = frozenset({
    "index",
    "workspace",
    "login",
    "connect",
    "static",
    "get_ai_settings",
    "update_ai_settings",
    "reload_ai_settings",
    "test_ai_settings",
    "api_inventory",
    "api_create_session",
    "api_update_session",
    "api_delete_session",
    "api_move_session",
    "api_connect_session",
    "api_disconnect_session",
    "api_reconnect_session",
    "api_session_status",
    "api_credentials_lookup",
    "api_get_prompt_context",
    "api_put_prompt_context",
    "api_benchmark_targets",
    "api_benchmark_status",
    "api_benchmark_start",
    "api_benchmark_stop",
})


def _max_ai_requests() -> int:
    return get_settings().openai_max_num_of_reqs


def _debug_enabled() -> int:
    return get_settings().debug


app = Flask(
    __name__,
    template_folder=str(TEMPLATES_DIR),
    static_folder=str(STATIC_DIR),
    static_url_path="/static",
)
app.config["SECRET_KEY"] = "your_secret_key"
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = str(SESSIONS_DIR / "flask_session")
Session(app)

ENTRY_TYPES = {
    "fact": {"add": "add_facts", "remove": "remove_fact"},
    "hint": {"add": "add_hint", "remove": "remove_hint"},
    "avoid": {"add": "add_avoid", "remove": "remove_avoid"},
    "demo": {"add": "add_demo", "remove": "remove_demo"}
}

_CERT_FILE = str(CERTS_DIR / "cert.pem")
_KEY_FILE = str(CERTS_DIR / "key.pem")
socketio = SocketIO(app, ssl_context=(_CERT_FILE, _KEY_FILE))


# Dictionary to hold SSH shells (keyed by inventory session id)
ssh_shells = {}
ssh_ssh_conns = {}
prompt_delimiters = {}
prompts = {}
loop = {}
beroots = {}
last_commands = {}
# session_id -> True when Full AI detects root (benchmark + UI)
root_won_by_session = {}
timeout_default = 6
prompt_delimiter = b"$ "  # Assuming the prompt ends with $ and a space
shell_recvuntil_v4_list = []


def resolve_server_session_id():
    """Active inventory session id from JSON body or Flask session."""
    data = request.get_json(silent=True) or {}
    return (
        data.get("server_session_id")
        or session.get("active_server_session_id")
        or session.get("sid")
        or getattr(session, "sid", None)
    )


def emit_session(session_id, data, color=None):
    payload = {"data": data, "server_session_id": session_id}
    if color is not None:
        payload["color"] = color
    socketio.emit("message", payload, namespace="/get", to=session_id)
    try:
        if session_id:
            get_session_logger(session_id).ui(str(data))
    except Exception:  # noqa: BLE001
        pass


def close_ssh_connection(session_id):
    shell = ssh_shells.pop(session_id, None)
    conn = ssh_ssh_conns.pop(session_id, None)
    prompts.pop(session_id, None)
    prompt_delimiters.pop(session_id, None)
    last_commands.pop(session_id, None)
    beroots.pop(session_id, None)
    loop.pop(session_id, None)
    flag = stop_full_ai_by_session.pop(session_id, None)
    if flag:
        flag.set()
    try:
        if shell is not None:
            shell.close()
    except Exception:
        pass
    try:
        if conn is not None:
            conn.close()
    except Exception:
        pass


def login_required(f):
    """Soft gate: workspace is open; SSH routes still check for a live shell."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated_function

@socketio.on('connect', namespace='/get')
def test_connect():
    print('Client connected')

@socketio.on('join', namespace='/get')
def on_join(data):
    session_id = (data or {}).get('server_session_id')
    if session_id:
        join_room(session_id)
        emit('message', {
            'data': f'[*] Subscribed to session {session_id[:8]}…',
            'color': '#8b949e',
            'server_session_id': session_id,
        })

@socketio.on('leave', namespace='/get')
def on_leave(data):
    session_id = (data or {}).get('server_session_id')
    if session_id:
        leave_room(session_id)

@socketio.on('disconnect', namespace='/get')
def test_disconnect():
    print('Client disconnected')

def send_time():
    while True:
        socketio.sleep(1)  # Sleep for 1 second
        time_str = time.strftime('%H:%M:%S')  # Get current time
        socketio.emit('message', {'data': 'Current time: ' + time_str}, namespace='/get')

@app.route('/')
def index():
    """Primary multi-session workspace (no forced connect form)."""
    return render_template('workspace.html')


@app.route('/workspace')
def workspace():
    return render_template('workspace.html')


@app.route('/terminal')
def terminal_legacy():
    """Legacy full-page terminal kept for compatibility."""
    hostname = session.get('hostname', 'host')
    username = session.get('username', 'user')
    return render_template('index.html', hostname=hostname, username=username)

@app.route('/login')
def login():
    return render_template('login.html')

def _sh_single_quote(value: str) -> str:
    """Escape a string for safe inclusion inside shell single quotes."""
    return "'" + str(value or "").replace("'", "'\"'\"'") + "'"


def upload_and_run_beroot(ssh_conn, *, password: str, slog=None, timeout: int = 180) -> str:
    """
    Upload tools/beroot/Linux to /tmp/Linux on the remote host, run BeRoot,
    and return the scanner stdout (also written remotely to /tmp/beroot.txt).
    """
    ensure_runtime_dirs()
    if not BEROOT_DIR.is_dir() or not (BEROOT_DIR / "beroot.py").is_file():
        raise FileNotFoundError(f"BeRoot package missing at {BEROOT_DIR}")

    if slog is not None:
        slog.info(f"beroot: uploading {BEROOT_DIR} → /tmp/")
    # pwntools uploads the directory itself, landing as /tmp/Linux/
    ssh_conn.upload(str(BEROOT_DIR), "/tmp/")

    pw = _sh_single_quote(password)
    # cd into the package so `from beroot.run import run` resolves.
    remote_cmd = (
        "cd /tmp/Linux && "
        "{ python3 beroot.py --password "
        + pw
        + " || python beroot.py --password "
        + pw
        + "; } > /tmp/beroot.txt 2>&1; "
        "echo __BEROOT_EXIT__:$?; "
        "wc -c /tmp/beroot.txt"
    )
    if slog is not None:
        slog.info("beroot: starting remote scan (this can take a minute)")

    runner = ssh_conn.process("/bin/sh", env={"TERM": ""})
    try:
        # Drain banner / prompt noise briefly
        recv_for_duration(runner, 1.0)
        runner.sendline(remote_cmd.encode() if isinstance(remote_cmd, str) else remote_cmd)
        deadline = time.time() + max(30, int(timeout))
        buf = b""
        while time.time() < deadline:
            try:
                chunk = runner.recv(timeout=2)
            except Exception:  # noqa: BLE001
                chunk = b""
            if chunk:
                buf += chunk
                if b"__BEROOT_EXIT__:" in buf:
                    # Grab trailing wc line
                    try:
                        buf += runner.recv(timeout=2)
                    except Exception:  # noqa: BLE001
                        pass
                    break
        else:
            # Timed out — still try to read whatever is left and the output file.
            if slog is not None:
                slog.warning(f"beroot: remote scan timed out after {timeout}s — fetching partial output")
            extra = recv_for_duration(runner, 2)
            if extra:
                buf += extra
    finally:
        try:
            runner.close()
        except Exception:  # noqa: BLE001
            pass

    # Prefer the file BeRoot wrote; fall back to captured stdout.
    text = ""
    try:
        raw = ssh_conn.download_data("/tmp/beroot.txt")
        if isinstance(raw, bytes):
            text = raw.decode("utf-8", errors="replace")
        else:
            text = str(raw or "")
    except Exception as exc:  # noqa: BLE001
        if slog is not None:
            slog.warning(f"beroot: download /tmp/beroot.txt failed: {exc}")
        text = buf.decode("utf-8", errors="replace")

    text = (text or "").strip()
    if not text:
        raise RuntimeError(
            "BeRoot produced empty output. "
            f"Remote buffer tail: {buf[-500:]!r}"
        )

    # BeRoot's sudo -ll parser often misses modern NOPASSWD listings; append a
    # plain `sudo -l` capture so privilege-escalation rules stay visible to the AI.
    try:
        probe = ssh_conn.process("/bin/sh", env={"TERM": ""})
        try:
            recv_for_duration(probe, 0.5)
            probe_cmd = (
                f"echo { _sh_single_quote(password) } | sudo -S -l 2>/dev/null; "
                "sudo -ln 2>/dev/null; echo __SUDO_L_DONE__"
            )
            probe.sendline(probe_cmd.encode())
            pbuf = b""
            p_end = time.time() + 20
            while time.time() < p_end:
                try:
                    chunk = probe.recv(timeout=1)
                except Exception:  # noqa: BLE001
                    chunk = b""
                if chunk:
                    pbuf += chunk
                    if b"__SUDO_L_DONE__" in pbuf:
                        break
            sudo_l = pbuf.decode("utf-8", errors="replace")
            sudo_l = sudo_l.split("__SUDO_L_DONE__")[0]
            # Drop shell echo of the command / prompt noise
            lines = [
                ln for ln in sudo_l.splitlines()
                if ln.strip() and not ln.strip().startswith("$")
                and "sudo -S -l" not in ln and "sudo -ln" not in ln
            ]
            sudo_clean = "\n".join(lines).strip()
            if sudo_clean and (
                "may run" in sudo_clean.lower()
                or "NOPASSWD" in sudo_clean
                or "sudoers" in sudo_clean.lower()
                or "(root)" in sudo_clean
            ):
                text = (
                    text
                    + "\n\n################ sudo -l (runner capture) ################\n\n"
                    + sudo_clean
                    + "\n"
                )
        finally:
            try:
                probe.close()
            except Exception:  # noqa: BLE001
                pass
    except Exception as exc:  # noqa: BLE001
        if slog is not None:
            slog.warning(f"beroot: sudo -l enrichment skipped: {exc}")

    if slog is not None:
        slog.info(f"beroot: scan finished ({len(text)} chars)")
        slog.block("BEROOT_OUTPUT", text[:20000])
    return text


def get_or_create_ssh_shell(session_id, create_new=False):
    if session_id in ssh_shells:
        return ssh_shells[session_id]
    elif create_new:
        try:
            # SSH connection setup (BeRoot is NOT uploaded here — Run tool does that)
            ssh_conn = ssh(
                user=session.get('username'),
                host=session.get('server'),
                port=session.get('port'),
                password=session.get('password'),
                timeout=10,
            )
            ssh_conn.set_env('TERM', '')

            # Opening a shell
            shell = ssh_conn.process('/bin/sh', env={'TERM': ''})
            shell_output_bytes, \
            shell_output_lines, \
            shell_output_lines_string, \
            shell_output = shell_recvuntil(shell, prompt_delimiter, drop=False, timeout=timeout_default)

            # Saving the shell and connection objects
            ssh_shells[session_id] = shell
            ssh_ssh_conns[session_id] = ssh_conn
            return shell
        except Exception as e:
            debug_logger.exception("Failed to create or use SSH shell.")
            raise e


def start_shell_listener(session_id):
    """Background recv loop scoped to one inventory session."""
    shell = ssh_shells.get(session_id)
    if shell is None:
        return
    session_data = {
        "sid": session_id,
        "hostname": session.get("hostname"),
        "username": session.get("username"),
        "password": session.get("password"),
        "server": session.get("server"),
        "port": session.get("port"),
    }
    stop_task_flag.clear()

    def _emit(event, data, namespace="/get", **kwargs):
        payload = dict(data or {})
        payload["server_session_id"] = session_id
        room = kwargs.pop("to", None) or session_id
        socketio.emit(event, payload, namespace=namespace, to=room, **kwargs)

    socketio.start_background_task(shell_interaction, shell, _emit, session_data)

@app.before_request
def check_authentication():
    # Local workspace app: allow inventory + settings without SSH login.
    # SSH command routes validate a live shell themselves.
    if request.endpoint in PUBLIC_ENDPOINTS or (request.endpoint or "").startswith("api_"):
        return
    if request.path.startswith("/api/") or request.path.startswith("/static"):
        return
    # Remaining privileged routes require at least one active inventory selection
    if request.endpoint in ("logout",):
        return
    return

@app.route('/connect', methods=['POST'])
def connect():
    try:
        credentials = request.get_json()
        username = credentials['username']
        password = credentials['password']
        server = credentials.get('server', 'default_host')
        hostname = credentials.get('hostname', "pehost")
        port = int(credentials.get('port', 22))
        if request.path == '/connect':
            session['logged_in'] = True
            session['username'] = username
            session['password'] = password
            session['server'] = server
            session['port'] = port
            session['hostname'] = hostname
            # Attempt to create SSH shell immediately after logging in
            session_id = session.sid
            try:
                shell = get_or_create_ssh_shell(session_id, create_new=True)
                
                priv_esc_prompt = PrivEscPrompt(username, password, "Linux", "root")
                prompts[session_id] = priv_esc_prompt
                prompt_delimiters[session_id] = b"$ "

                return jsonify(success=True)
            except Exception as e:
                return jsonify(success=False, error=str(e)), 500
        else:
            return jsonify(success=False), 401
    except Exception as e:
        socketio.emit('message', {'data': f"[ERROR] Failed to execute command - {e}"}, namespace='/get')
        debug_logger.exception("Failed to execute command.")
        return jsonify(error=str(e)), 500

@app.route('/get', methods=['GET'])
@login_required
def test():
    # formatted_string = template.format(cmd=cmd, resp=resp)
    time_str = time.strftime('%H:%M:%S')  # Get current time
    socketio.emit('message', {'data': 'Current time: 44' + time_str}, namespace='/get')
    return jsonify(output="response"), 200


def shell_conditions(command, shell, prompt_delimiter, session_data, just_got_root):
    # Handle special command cases
    if command.startswith("su "):
        while True:
            shell_output_bytes = recv_for_duration(shell, timeout_default)
            shell_output_lines = shell_output_bytes.decode('utf-8').split('\n')
            shell_output = shell_output_bytes.decode('utf-8').strip()
            priv_esc.add_history(f"{prompt_delimiter.decode('utf-8').strip()} {command}", shell_output)
            if len(shell_output) <= 0:
                break
            last_line = shell_output_lines[-1]
            if got_root(session_data.get('hostname'), last_line):
                prompt_delimiters[session_id] = last_line
                socketio.emit('message', {'data': f'{shell_output}\npwned!'}, namespace='/get')
                just_got_root = True
                summary = priv_esc.generate_summary()
                color = "#1E90FF"  # Determine the color based on your logic or data
                socketio.emit('message', {'data': f'{summary}\n', 'color': color}, namespace='/get')
                return 
                break
            if "Password:" in shell_output:
                debug_logger.info("password prompt detected (su)")
                shell.sendline(session_data.get('password'))
    if command.startswith("sudo ") and not command.startswith("sudo -l"):
        shell_output = recv_for_duration(shell, timeout_default).decode('utf-8').strip()
        priv_esc.add_history(f"{prompt_delimiter.decode('utf-8').strip()} {command}", shell_output)
        if f"password for {session_data.get('username')}" in shell_output:
            debug_logger.info("password prompt detected (sudo)")
            shell.sendline(session_data.get('password'))

    if "sudo " in command and not command.startswith("sudo -l"):
        priv_esc.add_history(f"{prompt_delimiter.decode('utf-8').strip()} {command}", shell_output)
        shell.sendline("!/bin/sh")
        priv_esc.add_history("!/bin/sh", shell_output)
        shell.sendline("id")
        priv_esc.add_history("id", shell_output)
        shell_output_bytes = recv_for_duration(shell, timeout_default)
        shell_output_lines = shell_output_bytes.decode('utf-8').split('\n')
        shell_output = shell_output_bytes.decode('utf-8').strip()
        for line in shell_output_lines:
            if got_root(session_data.get('hostname'), line):
                socketio.emit('message', {'data': f'{shell_output}\npwned!'}, namespace='/get')
                just_got_root = True
                prompt_delimiters[session_id] = shell_output_lines[-1]
                summary = priv_esc.generate_summary()
                color = "#1E90FF"  # Determine the color based on your logic or data
                socketio.emit('message', {'data': f'{summary}\n', 'color': color}, namespace='/get')
                return 
                break
    return command, shell, prompt_delimiter, session_data, just_got_root

def autonomous(session_data):
    global stop_task_flag

    with app.app_context():
        """Background task for a specific session using passed session data."""
        session_id = session_data['sid']
        slog = get_session_logger(session_id)
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
        
        # Safely fetching session-specific data with default values and debugging
        prompt_delimiter = prompt_delimiters.get(session_id, "$")  # Default to "#" if not set
        shell = ssh_shells.get(session_id)
        priv_esc = prompts.get(session_id)

        slog.info(f"initial shell={bool(shell)} prompt_delimiter={prompt_delimiter!r} priv_esc={bool(priv_esc)}")
        
        while i < max_reqs:  # Ensure the loop runs only if it's enabled
            if stop_flag.is_set():
                stop_reason = "stopped"
                slog.event("FULL_AI_STOP", "Stop flag set — exiting autonomous loop")
                break
            socketio.sleep(1)  # Non-blocking sleep for better SocketIO handling
            i += 1
            try:
                emit_session(session_id, f"AI request#{i}======================================================================", color="#f85149")
                slog.info(f"AI request#{i}")
                
                # Create a prompt
                prompt = priv_esc.generate_prompt()
                if _debug_enabled():
                    emit_session(session_id, f"[DEBUG] About to send prompt:\n{prompt}")
                
                # Prompt/response live in the session run log only (not debug.log).
                slog.debug(f"prompt #{i}:\n{prompt}")

                system = "You are an experienced pentester."
                response = get_answer(system, prompt)
                trimmed_ai_command = priv_esc.filter_output(response)
                command = normalize_ai_command(remove_matching_quotes(trimmed_ai_command))
                
                slog.ai_turn(
                    request_n=i,
                    system=system,
                    prompt=prompt or "",
                    raw_response=response or "",
                    filtered_command=command or "",
                )
                if not command:
                    slog.warning(f"AI returned empty/unusable command on request#{i}; skipping")
                    continue
                shell = ssh_shells.get(session_id) or shell
                if shell is None:
                    slog.error("No shell available before sendline — attempting reconnect")
                    if not _reconnect_shell_for_session(session_id, session_data, slog):
                        stop_reason = "reconnect_failed"
                        break
                    slog = get_session_logger(session_id)
                    shell = ssh_shells.get(session_id)
                shell.sendline(command)
                delim = prompt_delimiter.decode('utf-8').strip() if isinstance(prompt_delimiter, (bytes, bytearray)) else str(prompt_delimiter).strip()
                emit_session(session_id, f"{delim} {command}")
                slog.info(f"sent to shell: {delim} {command}")

                if not just_got_root:  
                    shell_output_bytes, \
                    shell_output_lines, \
                    shell_output_lines_string, \
                    shell_output = shell_recvuntil_v4(shell, prompt_delimiter, drop=False, timeout=1, session = session, emit_func = socketio.emit)

                    if shell_output is None:
                        slog.shell_io(
                            request_n=i,
                            command=command,
                            output="(None — recv timed out / no prompt delimiter)",
                            note="shell_recvuntil_v4 returned None",
                        )
                    else:
                        slog.shell_io(request_n=i, command=command, output=shell_output)
                    
                    # If it hangs (common after interactive priv-esc like vim/awk shells)
                    if shell_output == None:
                        emit_session(
                            session_id,
                            "[Debug] Autonomous() - timeout occurred, possibly stuck at prompt",
                            color="#FF0000",
                        )
                        slog.warning(f"recv timeout after command: {command!r}")
                        shell_output_bytes = recv_for_duration(shell, 4)
                        shell_output_lines  = shell_output_bytes.decode('utf-8').split('\n')
                        shell_output        = shell_output_bytes.decode('utf-8').strip()
                        shell_output_lines_string = str(shell_output_lines)
                        emit_session(session_id, shell_output or "(empty drain)")
                        slog.block(
                            f"HANG_RECOVERY_DRAIN #{i}",
                            f"after timeout drain:\n{shell_output}",
                        )

                        # Prefer answering sudo/su password prompts over hang-reconnect.
                        if _looks_like_password_prompt(shell_output):
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
                                timeout=3,
                                session=session,
                                emit_func=socketio.emit,
                            )
                            if more_out is None:
                                extra = recv_for_duration(shell, 3)
                                more_out = (after_pw or "") + "\n" + (
                                    extra.decode("utf-8", errors="replace") if extra else ""
                                )
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
                            # Nudge interactive editors / nested shells, then probe identity.
                            shell.sendline("!/bin/sh")
                            socketio.sleep(0.5)
                            shell.sendline("id")
                            socketio.sleep(0.5)
                            shell.sendline("id")
                            slog.info("hang recovery nudged: !/bin/sh then id x2")

                            shell_output_bytes = recv_for_duration(shell, 4)
                            shell_output_lines  = shell_output_bytes.decode('utf-8').split('\n')
                            shell_output        = shell_output_bytes.decode('utf-8').strip()
                            shell_output_lines_string = str(shell_output_lines)
                            if not shell_output_lines or shell_output_lines == ['']:
                                shell_output_lines = [shell_output]

                            emit_session(session_id, shell_output or "(empty post-hang probe)")
                            emit_session(
                                session_id,
                                "Start interacting with the shell again",
                                color="#1E90FF",
                            )
                            slog.shell_io(
                                request_n=i,
                                command="!/bin/sh ; id ; id",
                                output=shell_output,
                                note="post-hang probe before reconnect decision",
                            )

                            dump_path = slog.breakage(
                                "prompt_timeout_after_command",
                                command=command,
                                shell_output=shell_output,
                                needs_reconnect=True,
                                ai_request=i,
                                hint="Shell hung or dropped into an interactive editor; reconnect required",
                            )
                            debug_logger.warning(
                                f"[BREAKAGE] session={session_id} needs reconnect after command={command!r} dump={dump_path}"
                            )
                            emit_session(
                                session_id,
                                f"[BREAKAGE] Shell interaction lost — logged to {dump_path}. Reconnecting…",
                                color="#f85149",
                            )

                            hostname = session_data.get('hostname')
                            diagnosis = diagnose_root(hostname, shell_output)
                            if not diagnosis.get("got_root") and shell_output_lines:
                                for ln in shell_output_lines:
                                    dln = diagnose_root(hostname, ln)
                                    if dln.get("got_root"):
                                        diagnosis = dln
                                        break
                            slog.root_check(
                                request_n=i,
                                hostname=hostname or "",
                                last_line=(shell_output_lines[-1] if shell_output_lines else "") or "",
                                shell_output=shell_output or "",
                                won=bool(diagnosis.get("got_root")),
                                reasons=diagnosis,
                            )
                            # Keep the failed attempt in model history so it is not blindly retried.
                            priv_esc.add_history(
                                command,
                                (shell_output or "") + "\n[runner] command hung / lost shell prompt",
                            )
                            if diagnosis.get("got_root"):
                                last_line = shell_output_lines[-1] if shell_output_lines else shell_output
                                emit_session(session_id, f"{shell_output}\npwned!")
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

                            # Reconnect and continue Full AI if budget remains.
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
                                slog.info(f"continuing after reconnect; requests so far={i}; budget_left={reconnect_budget}")
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
                
                prompt = priv_esc.generate_prompt()

                hostname = session_data.get('hostname')
                diagnosis = diagnose_root(hostname, last_line)
                if not diagnosis.get("got_root"):
                    diagnosis = diagnose_root(hostname, shell_output)
                if not diagnosis.get("got_root") and shell_output_lines:
                    for ln in shell_output_lines:
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
                    emit_session(session_id, f"{shell_output}\npwned!")
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
                debug_logger.exception(f"full_ai.error session_id={session_id!r}")
                slog.exception(f"Failed to execute command: {e}")
                slog.event("ERROR", str(e), ai_request=i)
                emit_session(session_id, f"Error: {str(e)}")
                stop_reason = "error"
                break
        slog.event(
            "FULL_AI_END",
            "Autonomous loop finished",
            got_root=just_got_root,
            requests_run=i,
            stop_reason=stop_reason,
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
        try:
            from ramigpt.benchmark.orchestrator import mark_full_ai_finished
            mark_full_ai_finished(session_id)
        except Exception:
            pass


def execute_beroot(session_data):
    """
    Background task: upload BeRoot to the target, run it, pull results into the
    session prompt context, then optionally ask the AI for one follow-up command.
    """
    with app.app_context():
        session_id = session_data["sid"]
        slog = get_session_logger(session_id)
        ssh_conn = ssh_ssh_conns.get(session_id)
        shell = ssh_shells.get(session_id)
        delim = prompt_delimiters.get(session_id, b"$ ")
        if isinstance(delim, (bytes, bytearray)):
            prompt_delim_str = delim.decode("utf-8", errors="replace").strip()
        else:
            prompt_delim_str = str(delim).strip()

        if ssh_conn is None:
            emit_session(session_id, "[BeRoot] No SSH connection — connect first.", color="#f85149")
            loop[session_id] = 0
            return

        password = session_data.get("password") or ""
        slog.event(
            "BEROOT_START",
            "Uploading and running BeRoot on remote host",
            server=session_data.get("server"),
            port=session_data.get("port"),
            username=session_data.get("username"),
        )
        emit_session(session_id, "[BeRoot] Uploading toolkit to /tmp/Linux …", color="#58a6ff")
        debug_logger.info(
            f"beroot.start session_id={session_id!r} "
            f"host={session_data.get('server')!r}:{session_data.get('port')}"
        )

        try:
            beroot_string = upload_and_run_beroot(
                ssh_conn,
                password=password,
                slog=slog,
                timeout=180,
            )
        except Exception as exc:  # noqa: BLE001
            debug_logger.exception(f"beroot.failed session_id={session_id!r}")
            slog.exception(f"beroot failed: {exc}")
            slog.event("BEROOT_FAILED", str(exc))
            emit_session(session_id, f"[BeRoot] Failed: {exc}", color="#f85149")
            loop[session_id] = 0
            return

        # Persist a local copy for the session
        ensure_runtime_dirs()
        local_filename = str(BEROOT_DOWNLOADS_DIR / f"{session_id}_beroot.txt")
        try:
            Path(local_filename).write_text(beroot_string, encoding="utf-8")
            # Also try SFTP download so /tmp/beroot.txt and local stay aligned
            try:
                ssh_conn.download("/tmp/beroot.txt", local_filename)
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001
            slog.warning(f"beroot: could not write local copy: {exc}")

        beroots[session_id] = local_filename
        priv_esc = prompts.get(session_id)
        if priv_esc is not None:
            priv_esc.set_BeRoot(beroot_string)

        preview = beroot_string if len(beroot_string) < 12000 else (
            beroot_string[:6000] + "\n…[truncated]…\n" + beroot_string[-4000:]
        )
        emit_session(session_id, f"[BeRoot] Scan complete ({len(beroot_string)} chars):\n{preview}", color="#1E90FF")
        slog.event("BEROOT_OK", f"Scan complete ({len(beroot_string)} chars)", local_file=local_filename)
        debug_logger.info(f"beroot.ok session_id={session_id!r} chars={len(beroot_string)}")

        # Optional: ask the AI for one command informed by BeRoot findings.
        if priv_esc is None or shell is None:
            loop[session_id] = 0
            return
        try:
            prompt = priv_esc.generate_prompt()
            system = "You are an experienced pentester."
            response = get_answer(system, prompt)
            command = normalize_ai_command(remove_matching_quotes(priv_esc.filter_output(response)))
            if not command:
                emit_session(session_id, "[BeRoot] AI returned no follow-up command.", color="#8b949e")
                loop[session_id] = 0
                return
            slog.ai_turn(
                request_n=len(getattr(priv_esc, "history", []) or []) + 1,
                system=system,
                prompt=prompt or "",
                raw_response=response or "",
                filtered_command=command or "",
                source="beroot_followup",
            )
            last_commands[session_id] = command
            shell.sendline(command)
            emit_session(session_id, f"{prompt_delim_str} {command}")
        except Exception as exc:  # noqa: BLE001
            slog.warning(f"beroot AI follow-up skipped: {exc}")
            emit_session(session_id, f"[BeRoot] Scan saved; AI follow-up skipped: {exc}", color="#8b949e")
        finally:
            loop[session_id] = 0


@app.route('/action3', methods=['POST', 'DELETE'])
@login_required
def action3():
    if not request.is_json:
        debug_logger.warning("Request does not contain JSON data.")
        return jsonify(error="Invalid request format."), 400

    action = (request.json.get('action') or '').strip()
    if not action:
        return jsonify(error="Missing action parameter."), 400

    time_str = time.strftime('%H:%M:%S')

    if action == "start":
        session_id = resolve_server_session_id()
        if not session_id or session_id not in ssh_shells:
            return jsonify(error="No active SSH connection. Connect this session first."), 400
        if session_id not in ssh_ssh_conns:
            return jsonify(error="No SSH connection object for this session."), 400
        # Pause the interactive listener so it does not race BeRoot's helper shell.
        loop[session_id] = 1
        session_data_copy = {
            "sid": session_id,
            "username": session.get("username"),
            "password": session.get("password"),
            "hostname": session.get("hostname"),
            "server": session.get("server"),
            "port": session.get("port"),
        }
        socketio.start_background_task(execute_beroot, session_data_copy)
        emit_session(session_id, "Starting BeRoot (upload + scan)…", color="#58a6ff")
        return jsonify(output="beroot_started", session_id=session_id), 200

    elif action == "stop":
        session_id = resolve_server_session_id()
        if session_id:
            loop[session_id] = 0
            emit_session(session_id, "Stopping…", color="#8b949e")
        debug_logger.info(f"Action '{action}' triggered at {time_str}.")
        return jsonify(output="response"), 200

    else:
        debug_logger.warning(f"Invalid action received: {action}")
        return jsonify(error="Invalid action specified."), 400


@app.route('/action1', methods=['POST', 'DELETE'])
@login_required
def action1():
    debug_logger.debug("Received request at /action1 endpoint.")
    
    if not request.is_json:
        debug_logger.warning("Request does not contain JSON data.")
        return jsonify(error="Invalid request format."), 400

    action = request.json.get('action', '').strip()
    debug_logger.debug(f"Action received: {action}")

    if not action:
        debug_logger.warning("No action specified in the request.")
        return jsonify(error="Missing action parameter."), 400

    time_str = time.strftime('%H:%M:%S')  # Get current time
    session_id = resolve_server_session_id()
    if not session_id or session_id not in ssh_shells:
        return jsonify(error="No active SSH connection. Connect this session first."), 400

    session["active_server_session_id"] = session_id
    session_data = {
        'sid': session_id,
        'username': session.get('username'),
        'password': session.get('password'),
        'hostname': session.get('hostname'),
        'server': session.get('server'),
        'port': session.get('port'),
    }

    if action == "start":
        flag = stop_full_ai_by_session.setdefault(session_id, threading.Event())
        flag.clear()
        root_won_by_session[session_id] = False
        loop[session_id] = 1
        get_session_logger(session_id).event(
            "FULL_AI_REQUESTED",
            "Full AI start requested from UI",
            hostname=session_data.get("hostname"),
            server=session_data.get("server"),
            port=session_data.get("port"),
        )
        socketio.start_background_task(autonomous, session_data)

    elif action == "stop":
        flag = stop_full_ai_by_session.setdefault(session_id, threading.Event())
        flag.set()
        loop[session_id] = 0
        debug_logger.info(f"Action '{action}' triggered at {time_str}. Emitting 'Stopping..' message.")
        get_session_logger(session_id).event("FULL_AI_STOP_REQUESTED", "Stop Full AI requested from UI")
        emit_session(session_id, "Stopping Full AI…", color="#8b949e")

    else:
        debug_logger.warning(f"Invalid action received: {action}")
        return jsonify(error="Invalid action specified."), 400

    return jsonify(output="response"), 200

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

def shell_recvuntil(shell, prompt_delimiter, drop=False, timeout=timeout_default):
    shell_output_bytes  = shell.recvuntil(prompt_delimiter, drop=False, timeout=timeout_default)
    shell_output_lines  = shell_output_bytes.decode('utf-8').split('\n')
    shell_output        = shell_output_bytes.decode('utf-8').strip()
    shell_output_lines_string = str(shell_output_lines)
    return shell_output_bytes, shell_output_lines, shell_output_lines_string, shell_output

def shell_recvuntil_v2(shell, prompt_delimiter, drop=False, timeout=timeout_default, session = None, emit_func = None):
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

def shell_recvuntil_v4(shell, prompt_delimiter, drop=False, timeout=timeout_default, session=None, emit_func=None):
    with app.app_context():
        shell_output_bytes = b""
        shell_output = shell_output_bytes.decode('utf-8')
        shell_output_lines = shell_output.split('\n')
        shell_output_lines_string = str(shell_output_lines)
        
        #emit_func('message', {'data': '[Debug] shell_recvuntil_v4()', 'color': "#FF0000"}, namespace='/get')

        try:
            shell_output_bytes = shell.recvuntil(prompt_delimiter, drop=drop, timeout=timeout)
            #shell_output_bytes = shell.recv(drop=drop, timeout=timeout)
        except TimeoutError:
            # Handle the case where the recvuntil times out, possibly due to a sudo password prompt
            #emit_func('message', {'data': f"[Debug] {shell_output_lines_string}", 'color': "#1E90FF"}, namespace='/get')
            emit_func('message', {'data': '[Debug] Timeout occurred, possibly stuck at prompt', 'color': "#FF0000"}, namespace='/get')
            return None, None, None, None
        except Exception as e:
            #emit_func('message', {'data': f"[Debug] {shell_output_lines_string}", 'color': "#1E90FF"}, namespace='/get')
            debug_logger.error(f"shell_recvuntil_v4 error: {e}")
            emit_func('message', {'data': f"[Debug] shell_recvuntil_v4 - Error: {str(e)}", 'color': "#FF0000"}, namespace='/get')
            return None, None, None, None

        shell_output = shell_output_bytes.decode('utf-8')
        shell_output_lines = shell_output.split('\n')
        shell_output_lines_string = str(shell_output_lines)

        if len(shell_output_lines) == 1:
            if len(shell_output_lines[0]) == 0:
                #emit_func('message', {'data': f"[Debug] {shell_output_lines_string}", 'color': "#1E90FF"}, namespace='/get')
                emit_func('message', {'data': '[Debug] Empty response from shell, possibly stuck at prompt', 'color': "#FF0000"}, namespace='/get')
                return None, None, None, None

        emit_func('message', {'data': f"{shell_output}"}, namespace='/get')

        return shell_output_bytes, shell_output_lines, shell_output_lines_string, shell_output
    return None, None, None, None

def shell_interaction(shell, emit_func, session, max_retries=1000000):
    with app.app_context():
        session_id = session['sid']
        slog = get_session_logger(session_id)
        shell = ssh_shells.get(session_id)
        priv_esc = prompts.get(session_id)
        prompt_delimiter = prompt_delimiters.get(session_id, "$").strip()
        emit_func('message', {'data': "[Debug] Starting shell interaction", 'color': "#1E90FF"}, namespace='/get')
        slog.info("shell_interaction listener started")
        io_n = 0
        
        retries = 0
        
        while True:
            try:
                while True:
                    socketio.sleep(1)
                    #emit_func('message', {'data': f"[LOOP] 1\n", 'color': "#1E90FF"}, namespace='/get')
                    while not stop_task_flag.is_set():
                        #emit_func('message', {'data': f"[LOOP] 2\n", 'color': "#1E90FF"}, namespace='/get')
                        # Do not steal stdout while Full AI owns the shell.
                        if loop.get(session_id):
                            socketio.sleep(0.5)
                            continue
                        shell = ssh_shells.get(session_id)
                        socketio.sleep(1)
                        data = shell.recv(timeout=1)
                        if data:
                            prompt_delimiter = prompt_delimiters.get(session_id, "$").decode('utf-8').strip()
                            decoded_data = data.decode('utf-8').strip()
                            command = last_commands.get(session_id, "")
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
                            # Avoid ROOT_MISS spam on every `id`/`whoami`; keep wins + interesting probes.
                            if diagnosis.get("got_root") or ("uid=0" in (decoded_data or "")):
                                slog.root_check(
                                    request_n=io_n,
                                    hostname=hostname or "",
                                    last_line=(decoded_data.split("\n")[-1] if decoded_data else ""),
                                    shell_output=decoded_data or "",
                                    won=bool(diagnosis.get("got_root")),
                                    reasons=diagnosis,
                                )

                            emit_func('message', {'data': f"{decoded_data}\n"}, namespace='/get')

            except EOFError:
                debug_logger.warning(f"shell_interaction EOF session_id={session_id!r}")
                emit_func('message', {'data': "[Debug] Shell stream closed", 'color': "#FF0000"}, namespace='/get')
                retries += 1
                if retries < max_retries:
                    continue
            
            except Exception:
                retries += 1
                if retries < max_retries:
                    continue

            break  # Exit loop if no exceptions are raised
        
        slog.info("shell_interaction listener exited")
        emit_func('message', {'data': "[Debug] Exiting shell interaction", 'color': "#FF0000"}, namespace='/get')


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
        if ssh_conn is None:
            slog.info("No cached SSH connection — creating a new one")
            ssh_conn = ssh(
                user=session_data.get("username"),
                host=session_data.get("server"),
                port=int(session_data.get("port") or 22),
                password=session_data.get("password"),
                timeout=10,
            )
            ssh_conn.set_env("TERM", "")
            ssh_ssh_conns[session_id] = ssh_conn

        shell = ssh_conn.process("/bin/sh", env={"TERM": ""})
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
        return True
    except Exception as exc:  # noqa: BLE001
        slog.exception(f"RECONNECT_FAILED: {exc}")
        slog.event("RECONNECT_FAILED", str(exc))
        ssh_shells.pop(session_id, None)
        return False


def recreate_shell(emit_func, session_id):
    message = 'Exiting /bin/sh'
    debug_logger.debug(message)
    emit_func('message', {'data': message}, namespace='/get')
    ssh_conn = ssh_ssh_conns[session_id]
    shell = ssh_conn.process('/bin/sh', env={'TERM': ''})
    ssh_shells[session_id] = shell
    # After you start a new shell, drain the buffer using the recv function \/ 
    shell_output_bytes, \
    shell_output_lines, \
    shell_output_lines_string, \
    shell_output = shell_recvuntil_v2(shell, prompt_delimiter, drop=False, timeout=timeout_default, session = session)
    return jsonify(output='Started a new /bin/sh process'), 200

@app.route('/execute', methods=['POST'])
@login_required
def execute():
    global stop_task_flag
    stop_task_flag.clear()  # Make sure the flag is clear at the start

    session_id = resolve_server_session_id()
    if not session_id or session_id not in ssh_shells:
        debug_logger.warning("execute rejected: no active SSH session")
        return jsonify(error="No active SSH connection. Connect this session first."), 400

    session["active_server_session_id"] = session_id
    slog = get_session_logger(session_id)
    try:
        try:
            trimmed_ai_command = ""
            just_got_root = False
            prompt_delimiter = prompt_delimiters.get(session_id, "$")  
            shell = ssh_shells.get(session_id)
            priv_esc = prompts.get(session_id)

        except Exception as e:
            debug_logger.exception(f"execute setup failed session_id={session_id!r}")
            slog.exception(f"execute() setup failed: {e}")
            return jsonify(error=str(e)), 500

        # Create a prompt
        prompt = priv_esc.generate_prompt()

        command = request.json.get('command', '')
        from_ai = len(command) < 1
        if command == "exit":
            slog.event("SHELL_EXIT", "User requested exit — recreating /bin/sh")
            return recreate_shell(socketio.emit, session_id)

        if from_ai:
            system = "You are an experienced pentester."
            response = get_answer(system, prompt)
            trimmed_ai_command = priv_esc.filter_output(response)
            trimmed_ai_command = normalize_ai_command(remove_matching_quotes(trimmed_ai_command))
            command = trimmed_ai_command
            slog.ai_turn(
                request_n=len(getattr(priv_esc, "history", []) or []) + 1,
                system=system,
                prompt=prompt or "",
                raw_response=response or "",
                filtered_command=command or "",
                source="execute_ai",
            )
        else:
            slog.info(f"manual command requested: {command}")

        last_commands[session_id] = command
        shell.sendline(command)
        delim = prompt_delimiter.decode('utf-8').strip() if isinstance(prompt_delimiter, (bytes, bytearray)) else str(prompt_delimiter).strip()
        emit_session(session_id, f"{delim} {command}")
        slog.info(f"sent to shell ({'ai' if from_ai else 'manual'}): {delim} {command}")

        output = ""
        return jsonify(output=output), 200
    except Exception as e:
        sid = resolve_server_session_id()
        if sid:
            emit_session(sid, f"[ERROR] Failed to execute command - {e}", color="#f85149")
            get_session_logger(sid).exception(f"Failed to execute command: {e}")
        debug_logger.exception(f"execute failed session_id={session_id!r}")
        return jsonify(error=str(e)), 500

def modify_entry(entry_type, action):
    """ Generic function to add or remove an entry dynamically. """
    debug_logger.debug(f"Received request to {action} {entry_type}.")

    data = request.get_json() or {}
    text = data.get("text", "").strip()
    if not text:
        debug_logger.warning("Invalid or empty input received.")
        return jsonify(success=False, message="Invalid or empty input."), 400

    session_id = resolve_server_session_id()
    if not session_id:
        return jsonify(success=False, message="No session selected."), 400

    from ramigpt.services.session_store import get_session_store

    store = get_session_store()
    priv_esc = prompts.get(session_id)

    # If not connected yet, still allow editing persisted guidance for this session
    if priv_esc is None:
        try:
            ctx = store.get_prompt_context(session_id)
        except KeyError:
            return jsonify(success=False, message="Session not found."), 404
        bucket = {"fact": "facts", "hint": "hints", "avoid": "avoids"}.get(entry_type)
        if not bucket:
            return jsonify(success=False, message="Invalid operation."), 400
        items = list(ctx[bucket])
        if action == "add":
            if text not in items:
                items.append(text)
        else:
            items = [i for i in items if i != text]
        updated = store.set_prompt_context(session_id, **{bucket: items})
        return jsonify(
            success=True,
            message=f"{entry_type.capitalize()} {action}d successfully.",
            **updated,
        ), 200

    # Get the correct function dynamically
    function_name = ENTRY_TYPES.get(entry_type, {}).get(action)
    if not function_name:
        debug_logger.error(f"Invalid entry type '{entry_type}' or action '{action}' requested.")
        return jsonify(success=False, message="Invalid operation."), 400

    if not hasattr(priv_esc, function_name):
        debug_logger.error(f"Function '{function_name}' does not exist on the privilege escalation object.")
        return jsonify(success=False, message="Invalid operation."), 400

    try:
        # Execute the function dynamically
        getattr(priv_esc, function_name)(text)
        # Persist so reconnect / session switch keeps Facts, Hints, Avoid
        store.sync_prompt_lists_from_runtime(
            session_id, priv_esc.facts, priv_esc.hints, priv_esc.avoids
        )
        debug_logger.info(f"Successfully {action}d {entry_type}: {text}")
        return jsonify(
            success=True,
            message=f"{entry_type.capitalize()} {action}d successfully.",
            facts=list(priv_esc.facts),
            hints=list(priv_esc.hints),
            avoids=list(priv_esc.avoids),
        ), 200
    except Exception as e:
        debug_logger.exception(f"Error occurred while executing {function_name} for {entry_type}: {e}")
        return jsonify(success=False, message="Internal server error."), 500

# Single route for adding and deleting entries
@app.route('/<entry_type>', methods=['POST', 'DELETE'])
@login_required
def handle_entry(entry_type):
    if entry_type in ENTRY_TYPES:
        action = "add" if request.method == "POST" else "remove"
        return modify_entry(entry_type, action)
    return jsonify(success=False, message="Invalid entry type."), 400

@app.route('/logout')
def logout():
    # Disconnect active inventory session if present
    active = session.get("active_server_session_id")
    if active and active in ssh_shells:
        close_ssh_connection(active)
    session.clear()
    return redirect(url_for('index'))


from ramigpt.web.inventory_api import register_inventory_routes

register_inventory_routes(
    app,
    ssh_shells=ssh_shells,
    ssh_ssh_conns=ssh_ssh_conns,
    prompts=prompts,
    prompt_delimiters=prompt_delimiters,
    open_ssh_connection=get_or_create_ssh_shell,
    close_ssh_connection=close_ssh_connection,
    emit_session=emit_session,
    start_shell_listener=start_shell_listener,
)

from ramigpt.benchmark.api import register_benchmark_routes
from ramigpt.benchmark.orchestrator import register_benchmark_hooks

register_benchmark_hooks(
    flask_app=app,
    socketio=socketio,
    open_ssh_connection=get_or_create_ssh_shell,
    close_ssh_connection=close_ssh_connection,
    start_shell_listener=start_shell_listener,
    autonomous=autonomous,
    prompts=prompts,
    prompt_delimiters=prompt_delimiters,
    stop_full_ai_by_session=stop_full_ai_by_session,
    loop=loop,
    emit_session=emit_session,
)
register_benchmark_routes(app)


@app.route('/api/settings', methods=['GET'])
def get_ai_settings():
    """Return current AI / app settings for the settings UI."""
    return jsonify(get_settings().to_public_dict()), 200


@app.route('/api/settings', methods=['PUT', 'POST'])
def update_ai_settings():
    """Update AI settings in memory and persist them to .env."""
    if not request.is_json:
        return jsonify(error="Invalid request format."), 400

    payload = request.get_json(silent=True) or {}
    allowed = {
        "ai_provider",
        "openai_api_key",
        "openai_model",
        "openai_base_url",
        "openwebui_base_url",
        "openwebui_api_key",
        "openwebui_model",
        "openai_max_num_of_reqs",
        "debug",
    }
    updates = {key: payload[key] for key in allowed if key in payload}
    persist = bool(payload.get("persist", True))

    try:
        settings = get_settings_manager().update(updates, persist=persist)
        return jsonify(success=True, settings=settings.to_public_dict()), 200
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except Exception as exc:
        debug_logger.exception("Failed to update settings.")
        return jsonify(error=str(exc)), 500


@app.route('/api/settings/reload', methods=['POST'])
def reload_ai_settings():
    """Reload settings from the .env file (useful after manual edits)."""
    settings = get_settings_manager().reload()
    return jsonify(success=True, settings=settings.to_public_dict()), 200


@app.route('/api/settings/test', methods=['POST'])
def test_ai_settings():
    """
    Apply optional form settings (without requiring Save) and probe the provider
    with a tiny completion request.
    """
    payload = request.get_json(silent=True) or {}
    allowed = {
        "ai_provider",
        "openai_api_key",
        "openai_model",
        "openai_base_url",
        "openwebui_base_url",
        "openwebui_api_key",
        "openwebui_model",
        "openai_max_num_of_reqs",
        "debug",
    }
    updates = {key: payload[key] for key in allowed if key in payload}

    try:
        # Use form values for the probe; do not write .env unless Save was used.
        if updates:
            get_settings_manager().update(updates, persist=False)

        settings = get_settings()
        provider = create_provider(settings)
        reply = provider.create_completion(
            [
                {"role": "system", "content": "Reply with exactly: ok"},
                {"role": "user", "content": "ping"},
            ]
        )
        preview = (reply or "").strip().replace("\n", " ")
        if len(preview) > 80:
            preview = preview[:77] + "..."
        return jsonify(
            success=True,
            provider=settings.ai_provider,
            model=settings.active_model(),
            preview=preview,
        ), 200
    except Exception as exc:
        debug_logger.exception("AI connection test failed.")
        return jsonify(
            success=False,
            error=str(exc),
            provider=get_settings().ai_provider,
            model=get_settings().active_model(),
        ), 400


if __name__ == '__main__':
    # Prefer: python app.py (project root). Reloader defaults on via APP_RELOAD.
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "8443"))
    use_reloader = os.getenv("APP_RELOAD", "1").strip().lower() in {"1", "true", "yes", "on"}
    if use_reloader:
        app.config["TEMPLATES_AUTO_RELOAD"] = True
    socketio.run(
        app,
        host=host,
        port=port,
        debug=False,
        use_reloader=use_reloader,
        reloader_options={
            "exclude_patterns": [
                "*/data/*",
                "*/.git/*",
                "*/venv/*",
                "*/__pycache__/*",
                "*/certs/*",
                "*.pyc",
                "*.log",
            ],
        },
        keyfile=_KEY_FILE,
        certfile=_CERT_FILE,
        allow_unsafe_werkzeug=True,
        log_output=False,
    )

