"""
RamiGPT web application entry point.

This module is the public import surface for the Flask app. Implementation lives
in focused submodules under ``ramigpt.web`` — add new routes in ``routes/``,
shell logic in ``shell/``, scanner tools in ``tools/``, and Full AI in ``ai/``.
"""

from __future__ import annotations

# Bootstrap pwntools/logging before other web imports.
import ramigpt.web.bootstrap  # noqa: F401

from pwn import ssh

from ramigpt.web.extensions import (
    CERT_FILE,
    KEY_FILE,
    _CERT_FILE,
    _KEY_FILE,
    app,
    socketio,
)
from ramigpt.web.factory import create_web_app

# Shared state module (tests patch ``app.state`` for route-level mocks).
from ramigpt.web import state

# Web logging helpers (→ data/logs/debug.log + session run logs).
from ramigpt.web.logging_config import (
    configure_web_loggers,
    get_session_logger,
    log_app,
    log_app_exception,
    log_ssh_lifecycle,
)

# Re-export shared runtime state for inventory/benchmark hooks and tests.
from ramigpt.web.state import (
    _ai_tls,
    beroots,
    last_commands,
    linenums,
    linpeas_reports,
    loop,
    prompt_delimiter,
    prompt_delimiters,
    prompts,
    root_won_by_session,
    shell_listener_epoch,
    shell_recvuntil_v4_list,
    ssh_shells,
    ssh_ssh_conns,
    stop_full_ai,
    stop_full_ai_by_session,
    stop_task_flag,
    timeout_default,
)

# Session / prompt helpers
from ramigpt.web.prompt_helpers import (
    _debug_enabled,
    _generate_ai_prompt,
    _make_priv_esc_prompt,
    _seed_prompt_history,
    _strip_ansi,
    sanitize_beroot_for_prompt,
)
from ramigpt.web.session_emit import emit_session, resolve_server_session_id
from ramigpt.web.auth import login_required

# Shell layer
from ramigpt.web.shell.connection import (
    close_ssh_connection,
    get_or_create_ssh_shell,
    start_shell_listener,
    _open_ssh_interactive_shell,
)
from ramigpt.web.shell.reconnect import _reconnect_shell_for_session, recreate_shell
from ramigpt.web.shell.recv import (
    _interrupt_shell,
    _require_live_shell,
    _safe_decode,
    receive_shell_output,
    recv_for_duration,
)
from ramigpt.web.shell.password import (
    _answer_password_prompt,
    _looks_like_password_prompt,
    _still_waiting_on_password,
)
from ramigpt.web.shell.prompt_detect import (
    _is_shell_prompt_line,
    _looks_like_editor_stuck,
    _try_quit_editor,
)
from ramigpt.web.shell.recvuntil import (
    _session_v2_bridge,
    shell_recvuntil,
    shell_recvuntil_v2,
    shell_recvuntil_v3,
    shell_recvuntil_v4,
)
from ramigpt.web.shell.interaction import shell_interaction
from ramigpt.web.shell.ssh_remote import _sh_single_quote, _ssh_run_capture, _ssh_run_or_shell

# Tools
from ramigpt.web.tools.beroot import upload_and_run_beroot
from ramigpt.web.tools.scanners import execute_beroot, execute_linenum, execute_linpeas

# Full AI
from ramigpt.web.ai.autonomous import autonomous
from ramigpt.web.ai.tasks import start_autonomous_task
from ramigpt.web.ai.timing import _ai_sleep, _wait_or_stop

# Routes (tool executors exposed for tests)
from ramigpt.web.routes.ssh import (
    TOOL_EXECUTORS,
    _TOOL_EXECUTORS,
    _TOOL_LABELS,
    shell_conditions,
)

__all__ = [
    "app",
    "socketio",
    "CERT_FILE",
    "KEY_FILE",
    "_CERT_FILE",
    "_KEY_FILE",
    "create_web_app",
]
