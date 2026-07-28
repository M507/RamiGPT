"""Tiny completion probes for settings tests and benchmark warmup."""

from __future__ import annotations

from ramigpt.ai.base import ChatMessage

# Open WebUI external models (openai/gpt-5:*, etc.) return HTTP 200 + JSON ``null``
# when the system message is an instruction like "Reply with exactly: ok" while the
# user message is unrelated ("ping"). Keep probes to a single user turn.
PROVIDER_PROBE_MESSAGES: list[ChatMessage] = [
    {"role": "user", "content": "Reply with exactly: ok"},
]
