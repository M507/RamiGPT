"""Tiny completion probes for settings tests and benchmark warmup."""

from __future__ import annotations

from ramigpt.ai.base import ChatMessage

# Open WebUI OpenAI-proxied models (openai/gpt-*:*) return HTTP 200 + JSON ``null``
# for some imperative phrasings (notably ``Reply with exactly: ok``). Keep probes to
# a single plain user turn that those backends accept (verified: ``ping``, ``Say ok``).
PROVIDER_PROBE_MESSAGES: list[ChatMessage] = [
    {"role": "user", "content": "Say ok"},
]
