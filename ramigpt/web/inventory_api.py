"""Session inventory + connect/disconnect APIs for the workspace UI."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from flask import jsonify, request, session

from ramigpt.domain import PrivEscPrompt
from ramigpt.services.runtime_status import (
    all_statuses,
    clear_status,
    get_error,
    get_status,
    set_status,
)
from ramigpt.services.session_store import get_session_store
from ramigpt.utils import debug_logger
from ramigpt.utils.session_logging import (
    clear_all_data_logs,
    clear_terminal_buffer,
    get_session_logger,
    get_terminal_history,
    load_shell_command_history,
    start_session_log_run,
)


def register_inventory_routes(
    app,
    *,
    ssh_shells: dict,
    ssh_ssh_conns: dict,
    prompts: dict,
    prompt_delimiters: dict,
    open_ssh_connection: Callable[..., Any],
    close_ssh_connection: Callable[[str], None],
    emit_session: Callable[..., None],
    start_shell_listener: Callable[..., None],
    seed_prompt_history: Optional[Callable[..., Any]] = None,
):
    store = get_session_store()

    def _apply_history(session_id: str, prompt: PrivEscPrompt) -> None:
        if seed_prompt_history is not None:
            try:
                seed_prompt_history(session_id, prompt)
                return
            except Exception:  # noqa: BLE001
                pass
        try:
            prompt.merge_history_entries(load_shell_command_history(session_id))
        except Exception:  # noqa: BLE001
            pass

    @app.route("/api/inventory", methods=["GET"])
    def api_inventory():
        snap = store.snapshot()
        statuses = all_statuses()
        for sess in snap["sessions"]:
            sid = sess["id"]
            sess["status"] = get_status(sid)
            err = get_error(sid)
            if err:
                sess["error"] = err
            # If we have a live shell, force connected
            if sid in ssh_shells and sess["status"] == "disconnected":
                sess["status"] = "connected"
                set_status(sid, "connected")
        return jsonify(snap), 200

    @app.route("/api/sessions", methods=["POST"])
    def api_create_session():
        payload = request.get_json(silent=True) or {}
        try:
            sess = store.create_session(payload)
            public = store.snapshot()
            created = next(s for s in public["sessions"] if s["id"] == sess.id)
            created["status"] = "disconnected"
            return jsonify(success=True, session=created), 201
        except ValueError as exc:
            return jsonify(success=False, error=str(exc)), 400
        except Exception as exc:
            debug_logger.exception("create session failed")
            return jsonify(success=False, error=str(exc)), 500

    @app.route("/api/sessions/<session_id>", methods=["PUT", "PATCH"])
    def api_update_session(session_id: str):
        payload = request.get_json(silent=True) or {}
        try:
            store.update_session(session_id, payload)
            public = store.snapshot()
            updated = next(s for s in public["sessions"] if s["id"] == session_id)
            updated["status"] = get_status(session_id)
            return jsonify(success=True, session=updated), 200
        except KeyError:
            return jsonify(success=False, error="Session not found"), 404
        except ValueError as exc:
            return jsonify(success=False, error=str(exc)), 400

    @app.route("/api/sessions/<session_id>", methods=["DELETE"])
    def api_delete_session(session_id: str):
        try:
            if session_id in ssh_shells:
                close_ssh_connection(session_id)
            store.delete_session(session_id)
            clear_status(session_id)
            return jsonify(success=True), 200
        except KeyError:
            return jsonify(success=False, error="Session not found"), 404

    @app.route("/api/sessions/<session_id>/move", methods=["POST"])
    def api_move_session(session_id: str):
        payload = request.get_json(silent=True) or {}
        group_id = payload.get("group_id")
        if not group_id:
            return jsonify(success=False, error="group_id required"), 400
        try:
            store.move_session(session_id, group_id)
            return jsonify(success=True), 200
        except KeyError:
            return jsonify(success=False, error="Session not found"), 404

    @app.route("/api/sessions/<session_id>/connect", methods=["POST"])
    def api_connect_session(session_id: str):
        payload = request.get_json(silent=True) or {}
        saved = store.get_session(session_id)
        if not saved:
            return jsonify(success=False, error="Session not found"), 404

        set_status(session_id, "connecting")
        try:
            password = store.resolve_password(saved, payload.get("password"))
        except ValueError as exc:
            set_status(session_id, "error", str(exc))
            return jsonify(success=False, error=str(exc)), 400

        # Remember password if requested
        remember = payload.get("remember_credentials", saved.remember_credentials)
        if remember and payload.get("password"):
            store.update_session(
                session_id,
                {"password": payload["password"], "remember_credentials": True},
            )

        # Populate Flask session fields used by existing SSH helpers
        session["logged_in"] = True
        session["username"] = saved.username
        session["password"] = password
        session["server"] = saved.host
        session["port"] = saved.port
        session["hostname"] = saved.hostname or saved.name
        session["active_server_session_id"] = session_id

        try:
            # Close existing shell for this inventory id if reconnecting
            if session_id in ssh_shells:
                priv = prompts.get(session_id)
                if priv is not None:
                    store.sync_prompt_lists_from_runtime(
                        session_id, priv.facts, priv.hints, priv.avoids
                    )
                close_ssh_connection(session_id)

            open_ssh_connection(session_id, create_new=True)
            prompt = PrivEscPrompt(saved.username, password, "Linux", "root")
            # Restore per-session Facts / Hints / Avoid into the live AI context
            for fact in saved.facts or []:
                prompt.add_facts(fact)
            for hint in saved.hints or []:
                prompt.add_hint(hint)
            for avoid in saved.avoids or []:
                prompt.add_avoid(avoid)
            _apply_history(session_id, prompt)
            prompts[session_id] = prompt
            prompt_delimiters[session_id] = b"$ "
            set_status(session_id, "connected")
            store.touch_recent(session_id)
            start_shell_listener(session_id)
            slog = start_session_log_run(session_id, "connect")
            slog.event(
                "CONNECT",
                f"Connected to {saved.host}:{saved.port}",
                username=saved.username,
                hostname=saved.hostname,
                name=saved.name,
            )
            emit_session(
                session_id,
                f"[+] Connected to {saved.name} ({saved.host}:{saved.port})",
                color="#00ff00",
            )
            return jsonify(
                success=True,
                session_id=session_id,
                status="connected",
                username=saved.username,
                hostname=saved.hostname or saved.name,
                host=saved.host,
                port=saved.port,
                facts=list(prompt.facts),
                hints=list(prompt.hints),
                avoids=list(prompt.avoids),
            ), 200
        except Exception as exc:
            debug_logger.exception("connect failed")
            set_status(session_id, "error", str(exc))
            return jsonify(success=False, error=str(exc), status="error"), 500

    @app.route("/api/sessions/<session_id>/disconnect", methods=["POST"])
    def api_disconnect_session(session_id: str):
        try:
            # Persist live AI guidance before tearing down the SSH context
            priv = prompts.get(session_id)
            if priv is not None:
                store.sync_prompt_lists_from_runtime(
                    session_id, priv.facts, priv.hints, priv.avoids
                )
            close_ssh_connection(session_id)
            set_status(session_id, "disconnected")
            get_session_logger(session_id).event("DISCONNECT", "Session disconnected")
            emit_session(session_id, "[*] Disconnected", color="#8b949e")
            return jsonify(success=True, status="disconnected"), 200
        except Exception as exc:
            return jsonify(success=False, error=str(exc)), 500

    @app.route("/api/sessions/<session_id>/terminal", methods=["GET"])
    def api_session_terminal(session_id: str):
        """Scrollback for the workspace terminal (survives page refresh)."""
        try:
            store.get_session(session_id)
        except KeyError:
            return jsonify(error="Session not found"), 404
        try:
            limit = int(request.args.get("limit") or 800)
        except (TypeError, ValueError):
            limit = 800
        lines = get_terminal_history(session_id, limit=limit)
        return jsonify(
            session_id=session_id,
            lines=lines,
            count=len(lines),
            connected=session_id in ssh_shells,
        ), 200

    @app.route("/api/sessions/<session_id>/terminal", methods=["DELETE"])
    def api_clear_session_terminal(session_id: str):
        """Clear the live terminal scrollback for this session (UI clear)."""
        try:
            store.get_session(session_id)
        except KeyError:
            return jsonify(error="Session not found"), 404
        clear_terminal_buffer(session_id)
        return jsonify(success=True, session_id=session_id), 200

    @app.route("/api/sessions/<session_id>/prompt-context", methods=["GET"])
    def api_get_prompt_context(session_id: str):
        """Facts / Hints / Avoid for this inventory session (live or persisted)."""
        try:
            priv = prompts.get(session_id)
            if priv is not None:
                ctx = {
                    "facts": list(priv.facts),
                    "hints": list(priv.hints),
                    "avoids": list(priv.avoids),
                    "connected": True,
                }
            else:
                ctx = store.get_prompt_context(session_id)
                ctx["connected"] = False
            ctx["session_id"] = session_id
            return jsonify(ctx), 200
        except KeyError:
            return jsonify(error="Session not found"), 404

    @app.route("/api/sessions/<session_id>/prompt-context", methods=["PUT", "POST"])
    def api_put_prompt_context(session_id: str):
        """Replace Facts/Hints/Avoid for a session (used by Import)."""
        payload = request.get_json(silent=True) or {}
        try:
            facts = list(payload.get("facts") or [])
            hints = list(payload.get("hints") or [])
            avoids = list(payload.get("avoids") or [])
            ctx = store.set_prompt_context(
                session_id, facts=facts, hints=hints, avoids=avoids
            )
            priv = prompts.get(session_id)
            if priv is not None:
                priv.facts = list(facts)
                priv.hints = list(hints)
                priv.avoids = list(avoids)
            ctx["connected"] = session_id in ssh_shells
            ctx["session_id"] = session_id
            return jsonify(success=True, **ctx), 200
        except KeyError:
            return jsonify(success=False, error="Session not found"), 404

    @app.route("/api/sessions/<session_id>/reconnect", methods=["POST"])
    def api_reconnect_session(session_id: str):
        if session_id in ssh_shells:
            close_ssh_connection(session_id)
            set_status(session_id, "disconnected")
        return api_connect_session(session_id)

    @app.route("/api/sessions/<session_id>/status", methods=["GET"])
    def api_session_status(session_id: str):
        return jsonify(
            session_id=session_id,
            status=get_status(session_id),
            error=get_error(session_id),
            connected=session_id in ssh_shells,
        ), 200

    @app.route("/api/logs/clean", methods=["POST"])
    def api_clean_all_logs():
        """Delete folders under data/logs/ and truncate debug/times log files."""
        try:
            from ramigpt.benchmark.orchestrator import get_status as get_bench_status

            status = get_bench_status()
            if status.get("running"):
                return jsonify(
                    ok=False,
                    error="Stop the active benchmark before cleaning logs",
                ), 409
        except Exception:  # noqa: BLE001
            pass

        try:
            result = clear_all_data_logs(include_log_files=True)
            debug_logger.info(
                f"logs.clean removed={result.get('removed')} path={result.get('path')}"
            )
            return jsonify(ok=True, **result), 200
        except Exception as exc:  # noqa: BLE001
            debug_logger.exception("Failed to clean data/logs")
            return jsonify(ok=False, error=str(exc)), 500

    @app.route("/api/credentials/lookup", methods=["POST"])
    def api_credentials_lookup():
        payload = request.get_json(silent=True) or {}
        username = (payload.get("username") or "").strip()
        host = (payload.get("host") or "").strip()
        port = int(payload.get("port") or 22)
        pw = store.get_password(username, host, port)
        return jsonify(found=bool(pw), has_password=bool(pw)), 200
