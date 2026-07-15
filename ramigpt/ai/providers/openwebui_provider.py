"""Open WebUI provider (OpenAI-compatible ``/api/chat/completions``)."""

from __future__ import annotations

from typing import List, Optional

from openai import OpenAI

from ramigpt.ai.base import AIProvider, ChatMessage
from ramigpt.ai.providers.compat import (
    completion_text,
    ensure_suffix,
    make_openai_compat_client,
)
from ramigpt.config import Settings


class OpenWebUIProvider(AIProvider):
    """Talks to Open WebUI's OpenAI-compatible API (``{host}/api``)."""

    def __init__(self, settings: Settings, client: Optional[OpenAI] = None) -> None:
        if not settings.openwebui_base_url:
            raise ValueError("OPENWEBUI_BASE_URL is not configured.")

        base_url = ensure_suffix(settings.openwebui_base_url, "/api")
        api_key = settings.openwebui_api_key or settings.openai_api_key or "sk-placeholder"
        self._client = make_openai_compat_client(
            api_key=api_key, base_url=base_url, client=client
        )
        self._model = settings.openwebui_model
        self._base_url = base_url

    @property
    def name(self) -> str:
        return "openwebui"

    def create_completion(self, messages: List[ChatMessage]) -> str:
        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"AI provider openwebui request failed at {self._base_url} "
                f"(model={self._model!r}): {exc}"
            ) from exc
        return completion_text(completion)
