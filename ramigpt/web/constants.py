"""Shared web-layer constants (auth allowlists, entry types, tool labels)."""

from __future__ import annotations

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

ENTRY_TYPES = {
    "fact": {"add": "add_facts", "remove": "remove_fact"},
    "hint": {"add": "add_hint", "remove": "remove_hint"},
    "avoid": {"add": "add_avoid", "remove": "remove_avoid"},
    "demo": {"add": "add_demo", "remove": "remove_demo"},
}

TOOL_LABELS = {
    "beroot": "BeRoot",
    "linenum": "LinEnum",
    "linpeas": "LinPEAS",
}

DEFAULT_SHELL_TIMEOUT = 6
DEFAULT_PROMPT_DELIMITER = b"$ "
