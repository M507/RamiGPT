"""Sanitize prompts for Open WebUI external models.

Some Open WebUI-backed models (e.g. ``openai/gpt-5.2:latest``) respond with HTTP
200 and a literal JSON ``null`` body when the prompt contains GTFOBins-style shell
payloads, exploit write-ups, password-handling instructions, or a pentester system
role combined with privilege-escalation task text.
"""

from __future__ import annotations

import re

from ramigpt.ai.base import ChatMessage

_GTFObins_HEADER_RE = re.compile(r"^\s*\[?\+\]?\s*gtfobins found:", re.IGNORECASE)
_SECTION_HEADER_RE = re.compile(r"^\s*#{2,}\s*.+\s*#{2,}\s*$")
_SHELL_PAYLOAD_RE = re.compile(
    r"^\s*-\s*(?:echo|sudo)\s+.*(?:/bin/sh|/bin/bash|<\$\(tty\))",
    re.IGNORECASE,
)
_URL_LINE_RE = re.compile(r"^\s*(?:Details|Download URL):\s*https?://", re.IGNORECASE)
_URL_RE = re.compile(r"https?://\S+")
_PASSWORD_LINE_RE = re.compile(
    r"password.*runner supplies|never print or echo the password",
    re.IGNORECASE,
)
_PASSWORD_SENTENCE_RE = re.compile(
    r"\s*If a tool prompts for this account's password, the runner supplies it "
    r"automatically — never print or echo the password\.",
    re.IGNORECASE,
)

PENTESTER_SYSTEM = "You are an experienced pentester."
OPENWEBUI_SAFE_SYSTEM = "You are a helpful assistant."


def sanitize_for_openwebui(text: str) -> str:
    """Return prompt text safe for Open WebUI chat-completions API clients."""
    lines = (text or "").splitlines()
    cleaned: list[str] = []
    in_suid = False
    in_exploits = False
    skip_gtfo_block = False

    for line in lines:
        if _PASSWORD_LINE_RE.search(line):
            line = _PASSWORD_SENTENCE_RE.sub("", line).strip()
            if not line:
                continue

        header = line.strip().lower()
        if _SECTION_HEADER_RE.match(line.strip()):
            in_suid = "suid" in header
            in_exploits = "exploit" in header
            skip_gtfo_block = False
            if in_exploits:
                continue

        if in_exploits:
            continue

        if _GTFObins_HEADER_RE.match(line):
            skip_gtfo_block = True
            continue

        if skip_gtfo_block:
            stripped = line.strip()
            if not stripped:
                skip_gtfo_block = False
                continue
            if stripped.startswith("/") or _SECTION_HEADER_RE.match(stripped):
                skip_gtfo_block = False
            else:
                continue

        if in_suid and re.search(r"^\s*-\s*sudo\s+\S+", line):
            continue
        if _SHELL_PAYLOAD_RE.match(line):
            continue
        if _URL_LINE_RE.match(line):
            continue

        stripped = _URL_RE.sub("", line).rstrip()
        if stripped:
            cleaned.append(stripped)

    return re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned)).strip()


def prepare_openwebui_messages(messages: list[ChatMessage]) -> list[ChatMessage]:
    """Normalize chat messages before calling Open WebUI's OpenAI-compatible API."""
    prepared: list[ChatMessage] = []
    for msg in messages:
        role = str(msg.get("role") or "")
        content = str(msg.get("content") or "")
        if role == "system":
            if content.strip() == PENTESTER_SYSTEM or "pentester" in content.lower():
                content = OPENWEBUI_SAFE_SYSTEM
            else:
                content = sanitize_for_openwebui(content)
        elif role == "user":
            content = sanitize_for_openwebui(content)
        if content.strip():
            prepared.append({"role": role, "content": content})
    return prepared
