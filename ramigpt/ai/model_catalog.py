"""List available models per AI provider (for settings and benchmark UI)."""

from __future__ import annotations

from typing import List

from openai import OpenAI

from ramigpt.ai.providers.compat import ensure_suffix, openwebui_openai_base_url
from ramigpt.ai.providers.cursor_provider import DEFAULT_BASE_URL, list_cursor_model_details
from ramigpt.ai.providers.ollama_provider import list_ollama_models
from ramigpt.ai.providers.openrouter_provider import list_openrouter_models
from ramigpt.config import Settings, get_settings

_SUPPORTED = frozenset({"ollama", "openai", "openwebui", "openrouter", "cursor"})


def list_openai_compat_models(
    *,
    api_key: str,
    base_url: str,
    timeout: float = 8.0,
) -> List[str]:
    """Return model ids from an OpenAI-compatible ``GET /v1/models`` endpoint."""
    client = OpenAI(
        api_key=api_key or "sk-placeholder",
        base_url=(base_url or "").rstrip("/"),
        timeout=timeout,
        max_retries=0,
    )
    names: List[str] = []
    for item in client.models.list().data:
        model_id = getattr(item, "id", None)
        if model_id:
            names.append(str(model_id))
    return sorted(set(names), key=str.lower)


def saved_model_for_provider(settings: Settings, provider: str) -> str:
    provider = (provider or "").strip().lower()
    if provider == "ollama":
        return settings.ollama_model or ""
    if provider == "openai":
        return settings.openai_model or ""
    if provider == "openwebui":
        return settings.openwebui_model or ""
    if provider == "openrouter":
        return settings.openrouter_model or ""
    if provider == "cursor":
        return settings.cursor_model or ""
    return ""


def list_models_for_provider(provider: str, settings: Settings | None = None) -> List[str]:
    """Fetch installed/available models for a provider using saved settings."""
    cfg = settings or get_settings()
    name = (provider or "").strip().lower()
    if name not in _SUPPORTED:
        raise ValueError(f"Unsupported provider: {provider}")

    if name == "ollama":
        if not cfg.ollama_base_url:
            raise ValueError("Ollama base URL is not configured")
        return list_ollama_models(cfg.ollama_base_url, timeout=8.0)

    if name == "cursor":
        if not cfg.cursor_api_key:
            raise ValueError("Cursor API key is not configured")
        base_url = (cfg.cursor_base_url or DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
        details = list_cursor_model_details(cfg.cursor_api_key, base_url=base_url, timeout=8.0)
        return [item["id"] for item in details if item.get("id")]

    if name == "openai":
        if not cfg.openai_api_key:
            raise ValueError("OpenAI API key is not configured")
        base_url = (cfg.openai_base_url or "https://api.openai.com/v1").strip()
        if not base_url.endswith("/v1"):
            base_url = ensure_suffix(base_url, "/v1")
        return list_openai_compat_models(api_key=cfg.openai_api_key, base_url=base_url)

    if name == "openrouter":
        if not cfg.openrouter_api_key:
            raise ValueError("OpenRouter API key is not configured")
        return list_openrouter_models(
            cfg.openrouter_api_key,
            base_url=cfg.openrouter_base_url,
            timeout=8.0,
        )

    # openwebui
    if not cfg.openwebui_base_url:
        raise ValueError("Open WebUI base URL is not configured")
    api_key = cfg.openwebui_api_key or cfg.openai_api_key or "sk-placeholder"
    base_url = openwebui_openai_base_url(cfg.openwebui_base_url)
    return list_openai_compat_models(api_key=api_key, base_url=base_url)
