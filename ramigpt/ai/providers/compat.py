"""Shared helpers for OpenAI-compatible HTTP providers (Ollama, Open WebUI)."""

from __future__ import annotations

import re
from typing import Any, Optional

from openai import OpenAI

# Local/self-hosted models (cold load + long prompts) routinely exceed short
# cloud-style timeouts. Connect stays tight so dead hosts fail fast.
_DEFAULT_TIMEOUT_S = 600.0
_CONNECT_TIMEOUT_S = 5.0

_THINK_BLOCK_RE = re.compile(
    r"<think>.*?</think\s*>",
    flags=re.IGNORECASE | re.DOTALL,
)


def client_timeout():
    try:
        from httpx import Timeout

        return Timeout(_DEFAULT_TIMEOUT_S, connect=_CONNECT_TIMEOUT_S)
    except Exception:  # noqa: BLE001
        return _DEFAULT_TIMEOUT_S


def make_openai_compat_client(
    *,
    api_key: str,
    base_url: str,
    client: Optional[OpenAI] = None,
) -> OpenAI:
    if client is not None:
        return client
    return OpenAI(
        api_key=api_key or "sk-placeholder",
        base_url=base_url.rstrip("/"),
        timeout=client_timeout(),
        max_retries=0,
    )


def ensure_suffix(base_url: str, suffix: str) -> str:
    """Ensure base_url ends with ``suffix`` (e.g. ``/v1`` or ``/api``)."""
    url = (base_url or "").rstrip("/")
    if url.endswith(suffix):
        return url
    # Drop a conflicting OpenAI-compat suffix before appending the right one.
    for other in ("/v1", "/api"):
        if other != suffix and url.endswith(other):
            url = url[: -len(other)].rstrip("/")
            break
    return f"{url}{suffix}"


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
        return "".join(parts)
    return str(value)


def completion_text(completion: Any) -> str:
    """
    Extract assistant text from an OpenAI-compatible chat completion.

    Thinking models (e.g. Qwen3 via Ollama) may put the usable answer in
    ``content`` after a separate ``reasoning`` field, or leave ``content``
    empty mid-think. Prefer ``content``, then common reasoning fallbacks.
    """
    try:
        message = completion.choices[0].message
    except Exception:  # noqa: BLE001
        return ""

    content = _coerce_text(getattr(message, "content", None)).strip()
    if content:
        return _THINK_BLOCK_RE.sub("", content).strip()

    for attr in ("reasoning", "reasoning_content", "thinking"):
        fallback = _coerce_text(getattr(message, attr, None)).strip()
        if fallback:
            return fallback

    extra = getattr(message, "model_extra", None) or {}
    if isinstance(extra, dict):
        for key in ("reasoning", "reasoning_content", "thinking"):
            fallback = _coerce_text(extra.get(key)).strip()
            if fallback:
                return fallback
    return ""
