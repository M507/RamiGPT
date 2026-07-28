"""Wire Flask routes, Socket.IO handlers, and external API registrations."""

from __future__ import annotations

from ramigpt.web.auth import register_auth
from ramigpt.web.logging_config import log_app, register_request_logging
from ramigpt.web.extensions import app, socketio
from ramigpt.web.prompt_helpers import _seed_prompt_history
from ramigpt.web.routes.entries import register_entry_routes
from ramigpt.web.routes.pages import register_page_routes
from ramigpt.web.routes.settings import register_settings_routes
from ramigpt.web.routes.ssh import register_ssh_routes
from ramigpt.web.session_emit import emit_session
from ramigpt.web.shell.connection import (
    close_ssh_connection,
    get_or_create_ssh_shell,
    start_shell_listener,
)
from ramigpt.web.ai.autonomous import autonomous
from ramigpt.web.ai.tasks import start_autonomous_task
from ramigpt.web.tools.scanners import execute_beroot, execute_linenum, execute_linpeas
from ramigpt.web.state import (
    loop,
    prompt_delimiters,
    prompts,
    root_won_by_session,
    ssh_shells,
    ssh_ssh_conns,
    stop_full_ai_by_session,
)


def create_web_app():
    """Register all routes and hooks on the shared Flask/SocketIO instances."""
    register_request_logging(app)
    register_auth(app)
    register_page_routes(app)
    register_ssh_routes(app)
    register_entry_routes(app)
    register_settings_routes(app)

    # Socket handlers register via @socketio.on decorators on import.
    import ramigpt.web.sockets.handlers  # noqa: F401

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
        ssh_shells=ssh_shells,
        ssh_ssh_conns=ssh_ssh_conns,
        autonomous=autonomous,
        execute_beroot=execute_beroot,
        execute_linenum=execute_linenum,
        execute_linpeas=execute_linpeas,
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

    log_app("web.startup", status="ready")
    return app, socketio


# Eager registration on import (matches prior app.py behavior for tests/scripts).
create_web_app()
