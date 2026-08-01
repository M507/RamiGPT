"""Detect provider/model policy refusals that yield no runnable command."""

from __future__ import annotations

import re
from typing import Optional

# Clear policy / safety refusals (Anthropic Usage Policy, OpenAI refusals, etc.).
_POLICY_PATTERNS = (
    re.compile(r"violative\s+cyber\s+content", re.IGNORECASE),
    re.compile(r"blocked\s+under\s+\w+'?s?\s+usage\s+policy", re.IGNORECASE),
    re.compile(r"usage\s+policy", re.IGNORECASE),
    re.compile(r"content\s+policy", re.IGNORECASE),
    re.compile(r"against\s+(?:my|our)\s+(?:usage\s+)?(?:policy|guidelines)", re.IGNORECASE),
    re.compile(r"\b(?:i\s+)?(?:can'?t|cannot)\s+assist\s+with\b", re.IGNORECASE),
    re.compile(r"\b(?:i\s+)?(?:can'?t|cannot)\s+help\s+with\b", re.IGNORECASE),
    re.compile(r"refusals?-and-fallback", re.IGNORECASE),
)

POLICY_BLOCK_REASON = (
    "Model blocked this turn (usage / content policy violation)"
)


def detect_policy_violation(raw_response: str) -> Optional[str]:
    """
    Return a short UI reason when ``raw_response`` is a policy refusal.

    Returns ``None`` when the text does not look like a provider/model block.
    """
    text = " ".join(str(raw_response or "").split()).strip()
    if not text:
        return None
    for pattern in _POLICY_PATTERNS:
        if pattern.search(text):
            return POLICY_BLOCK_REASON
    return None
