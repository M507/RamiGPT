"""AI / app settings API routes."""

from __future__ import annotations

from flask import Flask, jsonify, request

from ramigpt.ai.factory import create_provider
from ramigpt.ai.probe import PROVIDER_PROBE_MESSAGES
from ramigpt.config import Settings, get_settings, get_settings_manager
from ramigpt.utils import debug_logger

_SETTINGS_ALLOWED = {
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
    "upgraded_session_v2",
    "advanced_mode",
    "terminal_tools_visible",
}


def register_settings_routes(app: Flask) -> None:
    @app.route("/api/settings", methods=["GET"])
    def get_ai_settings():
        """Return current AI / app settings for the settings UI."""
        return jsonify(get_settings().to_public_dict()), 200

    @app.route("/api/settings", methods=["PUT", "POST"])
    def update_ai_settings():
        """Persist user choices to JSON and API keys to .env."""
        if not request.is_json:
            return jsonify(error="Invalid request format."), 400

        payload = request.get_json(silent=True) or {}
        updates = {key: payload[key] for key in _SETTINGS_ALLOWED if key in payload}
        persist = bool(payload.get("persist", True))

        try:
            settings = get_settings_manager().update(updates, persist=persist)
            return jsonify(success=True, settings=settings.to_public_dict()), 200
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except Exception as exc:
            debug_logger.exception("Failed to update settings.")
            return jsonify(error=str(exc)), 500

    @app.route("/api/settings/reload", methods=["POST"])
    def reload_ai_settings():
        """Reload API keys/defaults from .env and user choices from JSON."""
        settings = get_settings_manager().reload()
        return jsonify(success=True, settings=settings.to_public_dict()), 200

    @app.route("/api/settings/ollama/models", methods=["GET", "POST"])
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

    @app.route("/api/settings/cursor/models", methods=["GET", "POST"])
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

    @app.route("/api/settings/openwebui/models", methods=["GET", "POST"])
    def list_openwebui_models_endpoint():
        """Return models from Open WebUI's OpenAI-compatible ``GET /api/v1/models``."""
        from ramigpt.ai.model_catalog import list_models_for_provider

        payload = request.get_json(silent=True) or {}
        cfg = get_settings()
        api_key = (
            (payload.get("openwebui_api_key") or request.args.get("api_key") or "").strip()
        )
        if not api_key or "..." in api_key or api_key.startswith("*"):
            api_key = cfg.openwebui_api_key
        base_url = (
            (payload.get("openwebui_base_url") or request.args.get("base_url") or "").strip()
            or cfg.openwebui_base_url
        )
        probe = Settings(
            ai_provider=cfg.ai_provider,
            openai_api_key=cfg.openai_api_key,
            openwebui_base_url=base_url,
            openwebui_api_key=api_key,
            openwebui_model=cfg.openwebui_model,
            ollama_base_url=cfg.ollama_base_url,
            ollama_api_key=cfg.ollama_api_key,
            ollama_model=cfg.ollama_model,
            cursor_api_key=cfg.cursor_api_key,
            cursor_model=cfg.cursor_model,
            cursor_base_url=cfg.cursor_base_url,
        )
        try:
            models = list_models_for_provider("openwebui", probe)
            return jsonify(
                success=True,
                base_url=base_url.rstrip("/"),
                models=models,
                count=len(models),
            ), 200
        except Exception as exc:  # noqa: BLE001
            debug_logger.warning(f"openwebui.list_models failed: {exc}")
            return jsonify(
                success=False,
                error=str(exc),
                base_url=base_url.rstrip("/") if base_url else "",
                models=[],
                count=0,
            ), 400

    @app.route("/api/settings/test", methods=["POST"])
    def test_ai_settings():
        """
        Apply optional form settings (without requiring Save) and probe the provider
        with a tiny completion request.
        """
        payload = request.get_json(silent=True) or {}
        updates = {key: payload[key] for key in _SETTINGS_ALLOWED if key in payload}

        try:
            if updates:
                get_settings_manager().update(updates, persist=False)

            settings = get_settings()
            provider = create_provider(settings)
            reply = provider.create_completion(list(PROVIDER_PROBE_MESSAGES))
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
