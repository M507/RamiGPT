"""Abstract AI provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, TypedDict


class ChatMessage(TypedDict):
    role: str
    content: str


class AIProvider(ABC):
    """Contract for chat-completion providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def create_completion(self, messages: List[ChatMessage]) -> str:
        """Return the assistant message content for the given chat history."""
        ...
