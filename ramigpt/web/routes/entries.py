"""Facts / hints / avoids CRUD routes."""

from __future__ import annotations

from flask import Flask, jsonify, redirect, request, session, url_for

from ramigpt.utils import debug_logger
from ramigpt.web.auth import login_required
from ramigpt.web.constants import ENTRY_TYPES
from ramigpt.web.session_emit import resolve_server_session_id
from ramigpt.web.shell.connection import close_ssh_connection
from ramigpt.web.state import prompts, ssh_shells

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


def register_entry_routes(app: Flask) -> None:
    @app.route("/<entry_type>", methods=["POST", "DELETE"])
    @login_required
    def handle_entry(entry_type):
        if entry_type in ENTRY_TYPES:
            action = "add" if request.method == "POST" else "remove"
            return modify_entry(entry_type, action)
        return jsonify(success=False, message="Invalid entry type."), 400

    @app.route("/logout")
    def logout():
        active = session.get("active_server_session_id")
        if active and active in ssh_shells:
            close_ssh_connection(active)
        session.clear()
        return redirect(url_for("index"))
