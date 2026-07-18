from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_session import Session
from flask_socketio import SocketIO, emit, join_room, leave_room
from functools import wraps
from pathlib import Path
import logging
import os
import re
import tarfile
import tempfile
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
# When Full AI runs on a real OS thread (benchmark worker), socketio.sleep is unsafe.
_ai_tls = threading.local()

from pwn import *
context.log_level = "error"
from ramigpt.ai import get_answer_with_usage
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
from ramigpt.utils.session_logging import load_shell_command_history
from ramigpt.config import (
    get_role_objective,
    get_rotated_role_objective,
    get_settings,
    get_settings_manager,
)
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


def _still_waiting_on_password(text: str) -> bool:
    """
    True only if the shell is *currently* stuck at a password prompt.
    Do not use whole-buffer substring checks — BeRoot follow-up drains often
    contain an earlier `[sudo] password for …` line even after `$` returns.
    """
    if not text:
        return False
    lines = [
        ln.strip()
        for ln in str(text).replace("\r", "\n").split("\n")
        if ln.strip()
    ]
    if not lines:
        return False
    last = lines[-1]
    # Recovered prompt means we are no longer waiting.
    if last in {"$", "#"} or last.endswith("$") or last.endswith("#"):
        return False
    return _looks_like_password_prompt(last)


def _answer_password_prompt(shell, session_data, slog=None) -> str:
    """Send the session password once and drain leftover prompt noise."""
    password = session_data.get("password") or ""
    if slog is not None:
        slog.info("answering password prompt (password not logged)")
    payload = password.encode() if isinstance(password, str) else password
    shell.sendline(payload)
    drained = recv_for_duration(shell, 2)
    return drained.decode("utf-8", errors="replace") if drained else ""


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text or "")


_URL_LINE_RE = re.compile(
    r"^\s*(?:Details|Download URL):\s*https?://",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://\S+")


def sanitize_beroot_for_prompt(beroot_text: str) -> str:
    """
    Prepare BeRoot output for the model: strip ANSI, drop misleading
    `sudo <bin>` GTFOBins lines from the SUID section (those binaries are SUID,
    not sudo rules — keeping them looks like fake NOPASSWD advice), and remove
    reference URLs (exploit write-ups, PoC download links) that waste prompt space.
    """
    text = _strip_ansi(beroot_text or "").strip()
    if not text:
        return text

    lines = text.splitlines()
    cleaned = []
    in_suid = False
    for line in lines:
        header = line.strip().lower()
        if header.startswith("################") and "suid" in header:
            in_suid = True
        elif header.startswith("################"):
            in_suid = False
        if in_suid and re.search(r"^\s*-\s*sudo\s+\S+", line):
            continue
        if _URL_LINE_RE.match(line):
            continue
        stripped = _URL_RE.sub("", line).rstrip()
        if stripped:
            cleaned.append(stripped)
    return "\n".join(cleaned).strip()

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
    "list_ollama_models_endpoint",
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
    "api_benchmark_verify_start",
    "api_benchmark_verify_status",
    "api_benchmark_verify_stop",
})


def _max_ai_requests() -> int:
    return get_settings().openai_max_num_of_reqs


def _debug_enabled() -> int:
    return get_settings().debug


def _generate_ai_prompt(priv_esc) -> str:
    settings = get_settings()
    role_objective = get_role_objective(settings.role_objective)
    if settings.rotate_role_objectives:
        rotation_base = getattr(priv_esc, "_role_rotation_base", None)
        if rotation_base != settings.role_objective:
            priv_esc._role_rotation_base = settings.role_objective
            priv_esc._role_rotation_offset = 0
        offset = getattr(priv_esc, "_role_rotation_offset", 0)
        _, role_objective = get_rotated_role_objective(
            settings.role_objective,
            offset,
        )
        priv_esc._role_rotation_offset = offset + 1
    else:
        priv_esc._role_rotation_base = settings.role_objective
        priv_esc._role_rotation_offset = 0
    return priv_esc.generate_prompt(
        include_history_outputs=bool(settings.history_include_outputs),
        history_output_edge_count=settings.history_output_edge_count,
        role_objective=role_objective,
    )


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

# session_id -> monotonic epoch so stale shell_interaction tasks exit quietly
shell_listener_epoch = {}
beroots = {}
last_commands = {}
# session_id -> history list stashed across disconnect/reconnect
_prompt_history_stash = {}
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
    # Persist first so a reconnect history reload cannot miss this line while the
    # websocket delivery is still in flight (or dropped because we left the room).
    try:
        if session_id:
            get_session_logger(session_id).ui(str(data), color=color)
    except Exception:  # noqa: BLE001
        pass
    payload = {"data": data, "server_session_id": session_id}
    if color is not None:
        payload["color"] = color
    socketio.emit("message", payload, namespace="/get", to=session_id)


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


def _seed_prompt_history(session_id, priv_esc) -> int:
    """
    Restore prior command history into a PrivEscPrompt.

    Prefers an in-memory stash from the last disconnect, then fills gaps from
    SHELL_IO events on disk (covers app restart / stopped Full AI loops).
    """
    if priv_esc is None:
        return 0
    added = 0
    stashed = _prompt_history_stash.pop(session_id, None) or []
    if stashed:
        added += int(priv_esc.merge_history_entries(stashed) or 0)
    try:
        from_logs = load_shell_command_history(session_id)
    except Exception:  # noqa: BLE001
        from_logs = []
    if from_logs:
        added += int(priv_esc.merge_history_entries(from_logs) or 0)
    return added


def _make_priv_esc_prompt(session_id, username, password, system, target_user):
    """Create a PrivEscPrompt and reseed command history for this session."""
    priv = PrivEscPrompt(username, password, system, target_user)
    seeded = _seed_prompt_history(session_id, priv)
    if seeded:
        debug_logger.info(
            f"prompt.history_seeded session_id={session_id!r} entries={len(priv.history)}"
        )
    return priv


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


def _pack_beroot_archive(dest: Path) -> None:
    """
    Pack tools/beroot/Linux into dest as Linux/... for remote extraction.

    Skips local scan downloads and macOS junk so the upload stays small/portable.
    """
    src = BEROOT_DIR
    with tarfile.open(dest, "w:gz") as tar:
        for path in sorted(src.rglob("*")):
            if path.name.startswith("._") or path.name in {".DS_Store", "__MACOSX"}:
                continue
            try:
                rel = path.relative_to(src)
            except ValueError:
                continue
            if rel.parts and rel.parts[0] == "downloaded":
                continue
            if not (path.is_file() or path.is_dir()):
                continue
            tar.add(path, arcname=str(Path("Linux") / rel), recursive=False)


def _upload_beroot_tree(ssh_conn, *, slog=None) -> None:
    """
    Upload BeRoot to /tmp/Linux without relying on remote GNU tar.

    pwntools upload_dir runs ``tar -xzf`` on the target; GNU tar 1.35 hits ENOSYS
    under some Docker/seccomp profiles (snap Docker + older kernels). Python's
    tarfile works on those same hosts, so pack locally and extract with python3.
    """
    remote_archive = "/tmp/ramigpt-beroot-linux.tgz"
    with tempfile.TemporaryDirectory(prefix="ramigpt-beroot-") as tmp:
        archive = Path(tmp) / "beroot-linux.tgz"
        _pack_beroot_archive(archive)
        if slog is not None:
            slog.info(
                f"beroot: uploading archive ({archive.stat().st_size} bytes) → {remote_archive}"
            )
        ssh_conn.upload(str(archive), remote_archive)

    extract_cmd = (
        "rm -rf /tmp/Linux && "
        "python3 -c "
        "\"import tarfile; tarfile.open('/tmp/ramigpt-beroot-linux.tgz','r:gz')"
        ".extractall('/tmp')\" && "
        "rm -f /tmp/ramigpt-beroot-linux.tgz && "
        "test -f /tmp/Linux/beroot.py"
    )
    if slog is not None:
        slog.info("beroot: extracting with remote python3 (avoids broken GNU tar)")
    buf = _ssh_run_or_shell(ssh_conn, extract_cmd, timeout=60, slog=slog)
    # Soft-check: command already ends with test -f; re-raise with buffer if needed.
    check = _ssh_run_or_shell(
        ssh_conn,
        "test -f /tmp/Linux/beroot.py && echo BEROOT_READY",
        timeout=10,
        slog=slog,
    )
    if b"BEROOT_READY" not in (check or b""):
        raise RuntimeError(
            "BeRoot upload/extract failed on remote host "
            f"(python3 extract). Tail: {(buf or b'')[-400]!r} / {(check or b'')[-400]!r}"
        )


def upload_and_run_beroot(ssh_conn, *, password: str, slog=None, timeout: int = 180) -> str:
    """
    Upload tools/beroot/Linux to /tmp/Linux on the remote host, run BeRoot,
    and return the scanner stdout (also written remotely to /tmp/beroot.txt).
    """
    ensure_runtime_dirs()
    if not BEROOT_DIR.is_dir() or not (BEROOT_DIR / "beroot.py").is_file():
        raise FileNotFoundError(f"BeRoot package missing at {BEROOT_DIR}")

    if slog is not None:
        slog.info(f"beroot: uploading {BEROOT_DIR} → /tmp/Linux")
    _upload_beroot_tree(ssh_conn, slog=slog)

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

    buf = _ssh_run_or_shell(
        ssh_conn, remote_cmd, timeout=max(30, int(timeout)), slog=slog
    )

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
        text = (buf or b"").decode("utf-8", errors="replace")

    text = (text or "").strip()
    if not text:
        raise RuntimeError(
            "BeRoot produced empty output. "
            f"Remote buffer tail: {(buf or b'')[-500:]!r}"
        )

    # BeRoot's sudo -ll parser often misses modern NOPASSWD listings; append a
    # plain `sudo -l` capture so privilege-escalation rules stay visible to the AI.
    try:
        probe_cmd = (
            f"echo {_sh_single_quote(password)} | sudo -S -l 2>/dev/null; "
            "sudo -ln 2>/dev/null; echo __SUDO_L_DONE__"
        )
        pbuf = _ssh_run_or_shell(ssh_conn, probe_cmd, timeout=20, slog=slog)
        sudo_l = (pbuf or b"").decode("utf-8", errors="replace")
        sudo_l = sudo_l.split("__SUDO_L_DONE__")[0]
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
    except Exception as exc:  # noqa: BLE001
        if slog is not None:
            slog.warning(f"beroot: sudo -l enrichment skipped: {exc}")

    if slog is not None:
        slog.info(f"beroot: scan finished ({len(text)} chars)")
        slog.block("BEROOT_OUTPUT", text[:20000])
    return text


def _require_live_shell(shell, *, where: str = "shell op"):
    """Raise a clear error instead of AttributeError on a dead/missing tube."""
    if shell is None:
        raise RuntimeError(
            f"{where}: SSH shell is None "
            "(process spawn failed, session disconnected, or connect never finished)"
        )
    return shell


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
        ("system:/bin/sh", lambda: ssh_conn.system("/bin/sh")),
        ("system:/bin/bash", lambda: ssh_conn.system("/bin/bash")),
        ("shell:/bin/bash", lambda: ssh_conn.shell("/bin/bash")),
        ("shell:/bin/sh", lambda: ssh_conn.shell("/bin/sh")),
    ):
        try:
            shell = opener()
            if shell is not None:
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
        return shell
    except Exception:
        debug_logger.exception("Failed to create or use SSH shell.")
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
                
                priv_esc_prompt = _make_priv_esc_prompt(
                    session_id, username, password, "Linux", "root"
                )
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
                socketio.emit('message', {'data': shell_output}, namespace='/get')
                socketio.emit('message', {'data': 'pwned!', 'color': '#ff0000'}, namespace='/get')
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
                socketio.emit('message', {'data': shell_output}, namespace='/get')
                socketio.emit('message', {'data': 'pwned!', 'color': '#ff0000'}, namespace='/get')
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
            provider=get_settings().ai_provider,
            model=get_settings().active_model(),
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
                response, usage = get_answer_with_usage(system, prompt)
                if stop_flag.is_set():
                    # LLM call already in flight isn't cancelled; discard the result.
                    stop_reason = "stopped"
                    slog.event(
                        "FULL_AI_STOP",
                        "Stop after AI response — discarding command, exiting",
                    )
                    break
                trimmed_ai_command = priv_esc.filter_output(response)
                command = normalize_ai_command(remove_matching_quotes(trimmed_ai_command))
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
                # Record immediately so a Stop / timeout still leaves the command
                # in history for the next Full AI run ("Do not repeat…").
                priv_esc.add_history(command, "")

                if not just_got_root:  
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
                        )
                    else:
                        slog.shell_io(request_n=i, command=command, output=shell_output)
                    
                    # If it hangs (common after interactive priv-esc like vim/awk shells)
                    if shell_output == None:
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


def _ai_sleep(seconds: float) -> None:
    """Sleep that is safe both on the eventlet hub and on OS threads."""
    if getattr(_ai_tls, "use_time_sleep", False):
        time.sleep(seconds)
        return
    try:
        socketio.sleep(seconds)
    except Exception:  # noqa: BLE001
        time.sleep(seconds)


def _wait_or_stop(stop_flag: threading.Event, seconds: float) -> bool:
    """Wait up to ``seconds``; return True if stop was requested (possibly early).

    Used between Full AI iterations so Stop wakes the inter-request delay instead
    of letting the next LLM call start after a blind sleep.
    """
    if stop_flag.is_set():
        return True
    if getattr(_ai_tls, "use_time_sleep", False):
        return bool(stop_flag.wait(timeout=seconds))
    deadline = time.monotonic() + max(0.0, float(seconds))
    while True:
        if stop_flag.is_set():
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return bool(stop_flag.is_set())
        _ai_sleep(min(0.05, remaining))


def start_autonomous_task(session_data: dict):
    """
    Start Full AI.

    - UI / Socket.IO greenlets: ``socketio.start_background_task`` (normal path).
    - Benchmark OS worker thread: a real ``threading.Thread`` with ``time.sleep``,
      because ``start_background_task`` / hub spawn from that thread never runs
      (benchmark suite 2336cf67… hung at FULL_AI_REQUESTED with no FULL_AI_START).
    """
    session_id = (session_data or {}).get("sid") or "unknown"
    use_os_thread = bool(
        (session_data or {}).get("use_os_thread")
        or (session_data or {}).get("inline_full_ai")
        or (session_data or {}).get("from_benchmark")
    )

    def _runner() -> None:
        if use_os_thread:
            _ai_tls.use_time_sleep = True
        try:
            autonomous(session_data)
        except Exception:  # noqa: BLE001
            debug_logger.exception(f"full_ai.crash session_id={session_id!r}")
            try:
                loop[session_id] = 0
            except Exception:  # noqa: BLE001
                pass
            try:
                from ramigpt.benchmark.orchestrator import mark_full_ai_finished
                mark_full_ai_finished(session_id)
            except Exception:  # noqa: BLE001
                pass
        finally:
            if use_os_thread:
                _ai_tls.use_time_sleep = False

    if use_os_thread:
        thread = threading.Thread(
            target=_runner,
            name=f"autonomous-{str(session_id)[:8]}",
            daemon=True,
        )
        thread.start()
        debug_logger.info(
            f"full_ai.spawn OS-thread session_id={session_id!r} thread={thread.name}"
        )
        return thread

    socketio.start_background_task(_runner)
    debug_logger.info(
        f"full_ai.spawn socketio.start_background_task session_id={session_id!r}"
    )
    return None


def execute_beroot(session_data):
    """
    Background task: upload BeRoot to the target, run it, attach findings to the
    session prompt, then optionally hand off to Full AI (when with_ai=True).
    """
    with app.app_context():
        session_id = session_data["sid"]
        with_ai = bool(session_data.get("with_ai", True))
        slog = get_session_logger(session_id)
        ssh_conn = ssh_ssh_conns.get(session_id)
        shell = ssh_shells.get(session_id)

        if ssh_conn is None:
            emit_session(session_id, "[BeRoot] No SSH connection — connect first.", color="#f85149")
            loop[session_id] = 0
            if with_ai:
                try:
                    from ramigpt.benchmark.orchestrator import mark_full_ai_finished
                    mark_full_ai_finished(session_id)
                except Exception:
                    pass
            return

        password = session_data.get("password") or ""
        slog.event(
            "BEROOT_START",
            "Uploading and running BeRoot on remote host",
            server=session_data.get("server"),
            port=session_data.get("port"),
            username=session_data.get("username"),
            with_ai=with_ai,
        )
        emit_session(
            session_id,
            f"[BeRoot] Uploading toolkit to /tmp/Linux … (AI={'on' if with_ai else 'off'})",
            color="#58a6ff",
        )
        debug_logger.info(
            f"beroot.start session_id={session_id!r} "
            f"host={session_data.get('server')!r}:{session_data.get('port')} with_ai={with_ai}"
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
            if with_ai:
                try:
                    from ramigpt.benchmark.orchestrator import mark_full_ai_finished
                    mark_full_ai_finished(session_id)
                except Exception:
                    pass
            return

        # Persist the enriched/sanitized text locally (do NOT re-download /tmp/beroot.txt
        # afterwards — that file lacks the sudo -l enrichment we append in-process).
        ensure_runtime_dirs()
        local_filename = str(BEROOT_DOWNLOADS_DIR / f"{session_id}_beroot.txt")
        beroot_for_ai = sanitize_beroot_for_prompt(beroot_string)
        try:
            Path(local_filename).write_text(beroot_for_ai, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            slog.warning(f"beroot: could not write local copy: {exc}")

        beroots[session_id] = local_filename
        priv_esc = prompts.get(session_id)
        if priv_esc is not None:
            # Persist BeRoot findings across Full AI turns when AI checkbox is on.
            priv_esc.set_BeRoot(beroot_for_ai, persist=with_ai)

        preview = beroot_for_ai if len(beroot_for_ai) < 12000 else (
            beroot_for_ai[:6000] + "\n…[truncated]…\n" + beroot_for_ai[-4000:]
        )
        emit_session(session_id, f"[BeRoot] Scan complete ({len(beroot_string)} chars):\n{preview}", color="#1E90FF")
        slog.event(
            "BEROOT_OK",
            f"Scan complete ({len(beroot_string)} chars)",
            local_file=local_filename,
            with_ai=with_ai,
        )
        debug_logger.info(f"beroot.ok session_id={session_id!r} chars={len(beroot_string)} with_ai={with_ai}")

        if not with_ai:
            loop[session_id] = 0
            emit_session(
                session_id,
                "[BeRoot] Done (AI off) — findings saved for later Full AI / Guide Me.",
                color="#8b949e",
            )
            return

        if priv_esc is None or shell is None:
            loop[session_id] = 0
            emit_session(
                session_id,
                "[BeRoot] Scan saved but cannot start Full AI (missing prompt or shell).",
                color="#f85149",
            )
            try:
                from ramigpt.benchmark.orchestrator import mark_full_ai_finished
                mark_full_ai_finished(session_id)
            except Exception:
                pass
            return

        # Hand off to the Full AI loop with BeRoot findings already in prompt context.
        flag = stop_full_ai_by_session.setdefault(session_id, threading.Event())
        flag.clear()
        root_won_by_session[session_id] = False
        loop[session_id] = 1
        slog.event("BEROOT_FULL_AI", "BeRoot finished — starting Full AI loop with scanner findings")
        emit_session(
            session_id,
            "[BeRoot] Handing off to Full AI with scanner findings…",
            color="#58a6ff",
        )
        get_session_logger(session_id).event(
            "FULL_AI_REQUESTED",
            "Full AI started after BeRoot (AI checkbox)",
            hostname=session_data.get("hostname"),
            server=session_data.get("server"),
            port=session_data.get("port"),
            source="beroot",
            provider=get_settings().ai_provider,
            model=get_settings().active_model(),
        )
        start_autonomous_task(session_data)


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
        # AI checkbox: default on. Accept ai / with_ai from the client.
        raw_ai = request.json.get("ai", request.json.get("with_ai", True))
        if isinstance(raw_ai, str):
            with_ai = raw_ai.strip().lower() not in {"0", "false", "no", "off"}
        else:
            with_ai = bool(raw_ai)
        # Pause the interactive listener so it does not race BeRoot's helper shell.
        loop[session_id] = 1
        session_data_copy = {
            "sid": session_id,
            "username": session.get("username"),
            "password": session.get("password"),
            "hostname": session.get("hostname"),
            "server": session.get("server"),
            "port": session.get("port"),
            "with_ai": with_ai,
        }
        socketio.start_background_task(execute_beroot, session_data_copy)
        emit_session(
            session_id,
            f"Starting BeRoot (upload + scan)… AI={'on' if with_ai else 'off'}",
            color="#58a6ff",
        )
        return jsonify(output="beroot_started", session_id=session_id, ai=with_ai), 200

    elif action == "stop":
        session_id = resolve_server_session_id()
        if session_id:
            # Do not clear loop here — autonomous/BeRoot finally clears it so the
            # interactive listener cannot steal prompts mid-command.
            flag = stop_full_ai_by_session.setdefault(session_id, threading.Event())
            flag.set()
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
            provider=get_settings().ai_provider,
            model=get_settings().active_model(),
        )
        start_autonomous_task(session_data)

    elif action == "stop":
        flag = stop_full_ai_by_session.setdefault(session_id, threading.Event())
        flag.set()
        # Keep loop[session_id]=1 until autonomous finally exits — otherwise the
        # interactive shell_interaction listener wakes mid-command and steals the
        # `$` prompt (see session 009: Stop during cat → false hang → reconnect).
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


def _is_shell_prompt_line(line: str) -> bool:
    """
    True for a real shell prompt on its own line.

    Critical: never treat a lone `$`/`#` byte substring in file dumps as a prompt —
    that desynchronizes the PTY (grep/cat of /etc containing `#` comments).
    """
    raw = (line or "").replace("\r", "")
    s = _strip_ansi(raw).strip()
    if not s or len(s) > 160:
        return False
    # Config / grep false positives
    if any(
        tok in s
        for tok in (
            '"',
            "'",
            "`",
            "\\$",
            "^/",
            "NO_DEL",
            "PATH=",
            "Defaults",
            "matching",
        )
    ):
        return False
    if s in {"$", "#", "%"}:
        return True
    if re.fullmatch(r"(?:bash|sh|zsh|ksh|dash)-[0-9.]+[#$]", s):
        return True
    # user@host:~/path$  or  root@host:/#
    if s.endswith("$") or s.endswith("#"):
        if "@" in s or "~" in s or ":/" in s or s.endswith(" $") or s.endswith(" #"):
            return True
        if re.search(r"\[[^\]]+\][#$]$", s):  # [root@box]#
            return True
    return False


def _interrupt_shell(shell) -> None:
    """Best-effort Ctrl-C to stop a runaway remote command."""
    if shell is None:
        return
    try:
        shell.send(b"\x03")
    except Exception:  # noqa: BLE001
        pass


def _looks_like_editor_stuck(text: str) -> bool:
    """True when drain/output shows an interactive vim/editor UI."""
    t = (text or "").lower()
    markers = (
        "type  :qa",
        "type :qa",
        "press <enter> to exit vim",
        "-- insert --",
        "-- replace --",
        "entering ex mode",
        "[no write since last change]",
        "e325: attention",
        "found a swap file",
    )
    return any(m in t for m in markers)


def _try_quit_editor(shell) -> str:
    """
    Escape an interactive vim (and similar) then force-quit.
    Returns whatever was drained after the quit attempts.
    """
    if shell is None:
        return ""
    try:
        shell.send(b"\x1b")  # ESC — leave insert / operator-pending
    except Exception:  # noqa: BLE001
        pass
    _ai_sleep(0.15)
    for payload in (b":qa!\r", b":q!\r", b"ZQ", b"\x03"):
        try:
            shell.send(payload)
        except Exception:  # noqa: BLE001
            pass
        _ai_sleep(0.2)
    return _safe_decode(recv_for_duration(shell, 1.5)).strip()


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

        command = request.json.get('command', '')
        from_ai = len(command) < 1
        if command == "exit":
            slog.event("SHELL_EXIT", "User requested exit — recreating /bin/sh")
            return recreate_shell(socketio.emit, session_id)

        if from_ai:
            prompt = _generate_ai_prompt(priv_esc)
            system = "You are an experienced pentester."
            response, usage = get_answer_with_usage(system, prompt)
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
                provider=get_settings().ai_provider,
                model=get_settings().active_model(),
                usage=usage,
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
    seed_prompt_history=_seed_prompt_history,
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
    execute_beroot=execute_beroot,
    prompts=prompts,
    prompt_delimiters=prompt_delimiters,
    stop_full_ai_by_session=stop_full_ai_by_session,
    seed_prompt_history=_seed_prompt_history,
    loop=loop,
    emit_session=emit_session,
    root_won_by_session=root_won_by_session,
    start_autonomous_task=start_autonomous_task,
)
register_benchmark_routes(app)


@app.route('/api/settings', methods=['GET'])
def get_ai_settings():
    """Return current AI / app settings for the settings UI."""
    return jsonify(get_settings().to_public_dict()), 200


@app.route('/api/settings', methods=['PUT', 'POST'])
def update_ai_settings():
    """Persist user choices to JSON and API keys to .env."""
    if not request.is_json:
        return jsonify(error="Invalid request format."), 400

    payload = request.get_json(silent=True) or {}
    allowed = {
        "ai_provider",
        "openai_api_key",
        "openai_model",
        "openai_base_url",
        "ollama_base_url",
        "ollama_api_key",
        "ollama_model",
        "openwebui_base_url",
        "openwebui_api_key",
        "openwebui_model",
        "cursor_api_key",
        "cursor_model",
        "cursor_base_url",
        "openai_max_num_of_reqs",
        "debug",
        "history_include_outputs",
        "history_output_edge_count",
        "role_objective",
        "rotate_role_objectives",
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
    """Reload API keys/defaults from .env and user choices from JSON."""
    settings = get_settings_manager().reload()
    return jsonify(success=True, settings=settings.to_public_dict()), 200


@app.route('/api/settings/ollama/models', methods=['GET', 'POST'])
def list_ollama_models_endpoint():
    """Return installed models from an Ollama host (``GET /api/tags``)."""
    from ramigpt.ai.providers.ollama_provider import list_ollama_models

    payload = request.get_json(silent=True) or {}
    base_url = (
        (payload.get("ollama_base_url") or request.args.get("base_url") or "").strip()
        or get_settings().ollama_base_url
    )
    try:
        models = list_ollama_models(base_url, timeout=8.0)
        return jsonify(
            success=True,
            base_url=base_url.rstrip("/"),
            models=models,
            count=len(models),
        ), 200
    except Exception as exc:  # noqa: BLE001
        debug_logger.warning(f"ollama.list_models failed: {exc}")
        return jsonify(
            success=False,
            error=str(exc),
            base_url=base_url.rstrip("/") if base_url else "",
            models=[],
            count=0,
        ), 400


@app.route('/api/settings/cursor/models', methods=['GET', 'POST'])
def list_cursor_models_endpoint():
    """Return recommended models from Cursor's Cloud Agents API (``GET /v1/models``)."""
    from ramigpt.ai.providers.cursor_provider import (
        DEFAULT_BASE_URL,
        list_cursor_model_details,
    )

    payload = request.get_json(silent=True) or {}
    api_key = (
        (payload.get("cursor_api_key") or request.args.get("api_key") or "").strip()
    )
    if not api_key or "..." in api_key or api_key.startswith("*"):
        api_key = get_settings().cursor_api_key
    base_url = (
        (payload.get("cursor_base_url") or request.args.get("base_url") or "").strip()
        or get_settings().cursor_base_url
        or DEFAULT_BASE_URL
    )
    try:
        details = list_cursor_model_details(api_key, base_url=base_url, timeout=8.0)
        models = [item["id"] for item in details]
        return jsonify(
            success=True,
            base_url=base_url.rstrip("/"),
            models=models,
            model_details=details,
            count=len(models),
        ), 200
    except Exception as exc:  # noqa: BLE001
        debug_logger.warning(f"cursor.list_models failed: {exc}")
        return jsonify(
            success=False,
            error=str(exc),
            base_url=base_url.rstrip("/") if base_url else "",
            models=[],
            model_details=[],
            count=0,
        ), 400


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
        "ollama_base_url",
        "ollama_api_key",
        "ollama_model",
        "openwebui_base_url",
        "openwebui_api_key",
        "openwebui_model",
        "cursor_api_key",
        "cursor_model",
        "cursor_base_url",
        "openai_max_num_of_reqs",
        "debug",
        "history_include_outputs",
        "history_output_edge_count",
        "role_objective",
        "rotate_role_objectives",
    }
    updates = {key: payload[key] for key in allowed if key in payload}

    try:
        # Use form values for the probe without writing JSON or .env.
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
    # Same startup clean as root app.py (no-op under reloader parent process).
    clean_on_start = os.getenv("APP_CLEAN_LOGS_ON_START", "1").strip().lower() in {
        "1", "true", "yes", "on",
    }
    run_startup = (not use_reloader) or os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    if clean_on_start and run_startup:
        try:
            from ramigpt.utils.session_logging import clear_all_data_logs

            result = clear_all_data_logs(include_log_files=True)
            debug_logger.info(
                f"logs.clean.startup removed={result.get('removed')} "
                f"path={result.get('path')}"
            )
            print(
                f"[RamiGPT] Cleared data/logs (removed={result.get('removed', 0)})",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[RamiGPT] Failed to clear data/logs: {exc}", flush=True)
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

