"""Abstract AI provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, TypedDict


class ChatMessage(TypedDict):
    role: str
    content: str


class AIProvider(ABC):
    """Contract for chat-completion providers."""

    # Set by create_completion() after each call (None if the backend does
    # not report usage). Callers read this immediately after the call since
    # provider instances are typically created fresh per request.
    last_usage: Optional[Dict[str, int]] = None

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def create_completion(self, messages: List[ChatMessage]) -> str:
        """Return the assistant message content for the given chat history."""
        ...
