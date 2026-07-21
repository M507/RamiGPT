"""Optional global serialization for AI provider HTTP/API calls."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Dict, Iterator, List, Optional

from ramigpt.ai.base import AIProvider, ChatMessage
from ramigpt.config import get_settings

_lock = threading.Lock()


def ai_request_queue_enabled() -> bool:
    try:
        return bool(int(get_settings().ai_request_queue))
    except (TypeError, ValueError):
        return False


@contextmanager
def ai_request_queue_lock() -> Iterator[None]:
    """When App Settings → AI request queuing is on, hold a process-wide lock."""
    if ai_request_queue_enabled():
        with _lock:
            yield
    else:
        yield


class QueuedAIProvider(AIProvider):
    """Wraps a provider so create_completion respects the optional global queue."""

    def __init__(self, inner: AIProvider) -> None:
        self._inner = inner
        self.last_usage: Optional[Dict[str, int]] = None

    @property
    def name(self) -> str:
        return self._inner.name

    def create_completion(self, messages: List[ChatMessage]) -> str:
        with ai_request_queue_lock():
            text = self._inner.create_completion(messages)
            self.last_usage = getattr(self._inner, "last_usage", None)
            return text
