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
_VIM_ROOT_PROBE = "sudo -n /usr/bin/vim -es -c ':!id' -c ':q!' /dev/null"
_VIM_WITH_EX = re.compile(
    r"^((?:sudo\s+)?(?:/(?:usr/)?bin/)?vim(?:\.basic)?)(\s+.*)?$",
    re.IGNORECASE | re.DOTALL,
)
_AWK_SUDO = re.compile(
    r"^sudo\s+(?:/(?:usr/)?bin/)?(?:gawk|mawk|nawk|awk)\b",
    re.IGNORECASE,
)
_AWK_SHELL_DROP = re.compile(
    r"""system\s*\(|sprintf\s*\(""",
    re.IGNORECASE,
)
_AWK_CANONICAL_PROBE = """sudo /usr/bin/awk 'BEGIN {system("id")}'"""


def _rewrite_interactive_sudo(command: str) -> str:
    """Turn interactive sudo shell drops into non-interactive root probes."""
    head = command.split("&&")[0].strip()
    if _INTERACTIVE_SUDO_SHELL.match(head):
        return "sudo -n id"
    if _SUDO_BARE_SHELL.match(head):
        return 'sudo -n bash -c "id; cat /root/flag.txt 2>/dev/null"'
    if _VISUDO.search(head):
        # visudo is rarely in sudoers; vim GTFOBins is the usual adjacent primitive.
        return _VIM_ROOT_PROBE
    return command


def _ensure_vim_ex_mode(command: str) -> str:
    """Prefer ex-mode vim for PTY runs (matches verify scripts, avoids full TUI)."""
    head = command.split("&&")[0].strip()
    match = _VIM_WITH_EX.match(head)
    if not match or re.search(r"(^|\s)-es\b", head):
        return command
    if not re.search(r"(^|\s)-c\b", head):
        return command
    return f"{match.group(1)} -es{match.group(2) or ''}"


def _rewrite_awk_shell_drop(command: str) -> str:
    """Collapse broken awk/gawk shell-drop one-liners onto the canonical id probe."""
    head = command.split("&&")[0].strip()
    if not _AWK_SUDO.match(head):
        return command
    if _AWK_SHELL_DROP.search(head):
        return _AWK_CANONICAL_PROBE
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
    rewritten = _rewrite_awk_shell_drop(rewritten)
    rewritten = _ensure_vim_ex_mode(rewritten)
    if _SUDO_BASH_C.match(rewritten.split("&&")[0].strip()):
        return rewritten
    return rewritten
