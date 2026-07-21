"""Factory for constructing the configured AI provider."""

from __future__ import annotations

from ramigpt.ai.base import AIProvider
from ramigpt.ai.request_queue import QueuedAIProvider
from ramigpt.ai.providers.cursor_provider import CursorProvider
from ramigpt.ai.providers.ollama_provider import OllamaProvider
from ramigpt.ai.providers.openai_provider import OpenAIProvider
from ramigpt.ai.providers.openwebui_provider import OpenWebUIProvider
from ramigpt.config import Settings, get_settings


def create_provider(settings: Settings | None = None) -> AIProvider:
    """Build a provider instance from settings (defaults to current config)."""
    cfg = settings or get_settings()
    provider = cfg.ai_provider

    if provider == "ollama":
        inner: AIProvider = OllamaProvider(cfg)
    elif provider == "openwebui":
        inner = OpenWebUIProvider(cfg)
    elif provider == "openai":
        inner = OpenAIProvider(cfg)
    elif provider == "cursor":
        inner = CursorProvider(cfg)
    else:
        raise ValueError(f"Unsupported AI provider: {provider}")
    return QueuedAIProvider(inner)


def get_provider() -> AIProvider:
    """Convenience alias that always uses the latest settings."""
    return create_provider()
