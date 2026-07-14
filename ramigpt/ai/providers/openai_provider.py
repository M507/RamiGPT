"""OpenAI chat-completions provider."""

from __future__ import annotations

from typing import List, Optional

from openai import OpenAI

from ramigpt.ai.base import AIProvider, ChatMessage
from ramigpt.config import Settings


class OpenAIProvider(AIProvider):
    """Thin wrapper around the official OpenAI SDK (unchanged defaults)."""

    def __init__(self, settings: Settings, client: Optional[OpenAI] = None) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not configured.")

        kwargs = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url

        self._client = client or OpenAI(**kwargs)
        self._model = settings.openai_model

    @property
    def name(self) -> str:
        return "openai"

    def create_completion(self, messages: List[ChatMessage]) -> str:
        completion = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
        )
        content = completion.choices[0].message.content
        return (content or "").strip()
