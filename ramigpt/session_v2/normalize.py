"""Command normalization and interactive-to-noninteractive rewrites for v2."""

from __future__ import annotations

import re
from typing import Optional

from ramigpt.domain.prompt import normalize_ai_command

_INTERACTIVE_SUDO_SHELL = re.compile(
    r"^sudo\s+(?:-i\b|-s\b|-\s|su(?:\s+-|\s*$))",
    re.IGNORECASE,
)
_SUDO_BARE_SHELL = re.compile(
    r"^sudo\s+(?:/(?:usr/)?bin/)?(?:ba)?sh\s*$",
    re.IGNORECASE,
)
_SUDO_BASH_C = re.compile(
    r"^sudo\s+(?:/(?:usr/)?bin/)?(?:ba)?sh\s+-c\s+",
    re.IGNORECASE,
)
_VISUDO = re.compile(r"\bvisudo\b", re.IGNORECASE)


def _rewrite_interactive_sudo(command: str) -> str:
    """Turn interactive sudo shell drops into non-interactive root probes."""
    head = command.split("&&")[0].strip()
    if _INTERACTIVE_SUDO_SHELL.match(head):
        return "sudo -n id"
    if _SUDO_BARE_SHELL.match(head):
        return 'sudo -n bash -c "id; cat /root/flag.txt 2>/dev/null"'
    if _VISUDO.search(head):
        return "sudo -n id"
    return command


def prepare_command(command: Optional[str]) -> Optional[str]:
    """
    Normalize and rewrite a model command for the autonomous runner.

    Applies the legacy ``normalize_ai_command`` first, then v2 interactive
    rewrites for sudo shell drops and disallowed editors.
    """
    if command is None:
        return None
    normalized = normalize_ai_command(command)
    if not normalized:
        return normalized
    rewritten = _rewrite_interactive_sudo(normalized)
    if _SUDO_BASH_C.match(rewritten.split("&&")[0].strip()):
        return rewritten
    return rewritten
