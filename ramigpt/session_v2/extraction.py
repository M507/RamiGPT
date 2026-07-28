"""Priority-based AI response → shell command extraction."""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Tuple

_FENCE_RE = re.compile(
    r"```(?:bash|sh|shell)?\s*\n?(.*?)```",
    re.IGNORECASE | re.DOTALL,
)
_BACKTICK_RE = re.compile(r"`([^`\n]+)`")

_PROSE_PREFIX = re.compile(
    r"^(?:the|this|to|command|next|\*\*|#|\d+\.|\*\*command\*\*|\*\*next command\*\*)",
    re.IGNORECASE,
)

_SHELL_HEAD = re.compile(
    r"^(?:sudo|su|id|whoami|cat|find|grep|ls|awk|gawk|vim|python|bash|sh|curl|wget|"
    r"less|nano|env|tar|perl|ruby|node|chmod|chown|cp|mv|rm|touch|echo|export|"
    r"unset|cd|pwd|uname|strings|file|stat|head|tail|wc|sort|uniq|xargs)\b",
    re.IGNORECASE,
)


def _clean_candidate(raw: str) -> str:
    line = (raw or "").strip()
    if not line:
        return ""
    if line.startswith("```"):
        line = re.sub(r"^```(?:bash|sh|shell)?\s*", "", line, flags=re.IGNORECASE)
        line = re.sub(r"\s*```$", "", line)
        line = line.strip()
    return line


def _is_usable_command(line: str) -> bool:
    if not line or len(line) > 4000:
        return False
    if _PROSE_PREFIX.match(line):
        return False
    if line.endswith(":") and not line.startswith("sudo"):
        return False
    if _SHELL_HEAD.match(line):
        return True
    if line.startswith("sudo ") or line.startswith("!/"):
        return True
    if re.match(r"^[/~\.]", line):
        return True
    return False


def _lines_from_fences(text: str) -> List[str]:
    out: List[str] = []
    for match in _FENCE_RE.finditer(text):
        block = match.group(1)
        for raw in block.splitlines():
            line = _clean_candidate(raw)
            if line and not line.startswith("#") and _is_usable_command(line):
                out.append(line)
    return out


def _lines_from_backticks(text: str) -> List[str]:
    out: List[str] = []
    for match in _BACKTICK_RE.finditer(text):
        line = _clean_candidate(match.group(1))
        if line and _is_usable_command(line):
            out.append(line)
    return out


def _lines_from_body(text: str) -> List[str]:
    out: List[str] = []
    for raw in text.splitlines():
        line = _clean_candidate(raw)
        if line and _is_usable_command(line):
            out.append(line)
    return out


def _pick_best(candidates: Iterable[Tuple[str, str]]) -> Optional[str]:
    """Prefer fenced > backtick > body; within a tier keep document order."""
    tiers = {"fence": 0, "backtick": 1, "body": 2}
    ranked = sorted(candidates, key=lambda item: (tiers.get(item[0], 9),))
    for _, command in ranked:
        if command:
            return command
    return None


def extract_command_from_response(text: str) -> Optional[str]:
    """
    Extract a single shell command from a model response.

    Unlike the legacy ``filter_output`` catch-all, prose paragraphs are never
    chosen when a fenced or backticked command is present.
    """
    if not text or not str(text).strip():
        return None

    body = str(text)
    candidates: List[Tuple[str, str]] = []
    for line in _lines_from_fences(body):
        candidates.append(("fence", line))
    for line in _lines_from_backticks(body):
        candidates.append(("backtick", line))
    for line in _lines_from_body(body):
        candidates.append(("body", line))

    return _pick_best(candidates)
