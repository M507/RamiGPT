"""Open WebUI provider (OpenAI-compatible ``/api/chat/completions``)."""

from __future__ import annotations

from typing import List, Optional

from openai import OpenAI

from ramigpt.ai.base import AIProvider, ChatMessage
from ramigpt.ai.openwebui_prompt import prepare_openwebui_messages
from ramigpt.ai.providers.compat import (
    make_openai_compat_client,
    openwebui_openai_base_url,
    require_chat_completion_text,
    usage_from_completion,
)
from ramigpt.config import Settings


class OpenWebUIProvider(AIProvider):
    """Talks to Open WebUI's OpenAI-compatible API (``{host}/api/v1``)."""

    def __init__(self, settings: Settings, client: Optional[OpenAI] = None) -> None:
        if not settings.openwebui_base_url:
            raise ValueError("OPENWEBUI_BASE_URL is not configured.")

        base_url = openwebui_openai_base_url(settings.openwebui_base_url)
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
        payload = prepare_openwebui_messages(messages)
        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=payload,
                stream=False,
                extra_body={"parent_id": None},
            )
        except Exception as exc:  # noqa: BLE001
            self.last_usage = None
            raise RuntimeError(
                f"AI provider openwebui request failed at {self._base_url} "
                f"(model={self._model!r}): {exc}"
            ) from exc
        self.last_usage = usage_from_completion(completion)
        return require_chat_completion_text(
            completion,
            provider=self.name,
            model=self._model,
            base_url=self._base_url,
        )
