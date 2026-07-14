"""Open WebUI provider (OpenAI-compatible /api/chat/completions)."""

from __future__ import annotations

from typing import List, Optional

from openai import OpenAI

from ramigpt.ai.base import AIProvider, ChatMessage
from ramigpt.config import Settings


def _normalize_openwebui_base_url(base_url: str) -> str:
    """
    OpenAI SDK appends `/chat/completions` to base_url.
    Open WebUI exposes completions at `{host}/api/chat/completions`,
    so the SDK base_url must end with `/api`.
    """
    url = (base_url or "").rstrip("/")
    if url.endswith("/v1"):
        return url
    if url.endswith("/api"):
        return url
    return f"{url}/api"


class OpenWebUIProvider(AIProvider):
    """Uses the OpenAI SDK against Open WebUI's compatible API surface."""

    def __init__(self, settings: Settings, client: Optional[OpenAI] = None) -> None:
        if not settings.openwebui_base_url:
            raise ValueError("OPENWEBUI_BASE_URL is not configured.")

        api_key = settings.openwebui_api_key or settings.openai_api_key or "sk-placeholder"
        base_url = _normalize_openwebui_base_url(settings.openwebui_base_url)

        self._client = client or OpenAI(api_key=api_key, base_url=base_url)
        self._model = settings.openwebui_model
        self._base_url = base_url

    @property
    def name(self) -> str:
        return "openwebui"

    def create_completion(self, messages: List[ChatMessage]) -> str:
        completion = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
        )
        content = completion.choices[0].message.content
        return (content or "").strip()
