"""Priority-based AI response → shell command extraction."""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Tuple

_FENCE_RE = re.compile(
    r"```(?:bash|sh|shell)?\s*\n?(.*?)```",
    re.IGNORECASE | re.DOTALL,
)
_BACKTICK_RE = re.compile(r"`([^`\n]+)`")

# Markdown / list decorations or an English word followed by a space — either
# way this line is prose, not a bare command. Requiring a trailing space keeps
# real single-token binaries safe (e.g. ``run`` matches "run the …" but never
# ``runuser``; ``to`` matches "to escalate …" but never ``touch``/``top``).
_PROSE_PREFIX = re.compile(
    r"^(?:\*\*|#\s|\d+[.)]\s|[-*]\s)"
    r"|^(?:the|this|these|to|next|here|we|let|first|now|use|run|note|then|also|"
    r"i|i'm|i'll|you|your|it|its|as|based|since|because|try|trying)\b[\s:]",
    re.IGNORECASE,
)

# Binaries the model routinely proposes for enumeration / privilege escalation.
# This is deliberately broad: silently dropping a legitimate command (e.g.
# `getcap`, `redis-cli`, `ss`) burns an entire AI turn and its tokens with no
# feedback, which previously caused runs to loop until timeout. The generic
# ``_looks_like_command`` fallback below catches the long tail.
_SHELL_HEAD = re.compile(
    r"^(?:"
    r"sudo|su|doas|id|whoami|hostname|uname|arch|lsb_release|"
    r"cat|tac|head|tail|less|more|nl|"
    r"find|locate|grep|egrep|fgrep|rg|ls|dir|stat|file|strings|readlink|realpath|basename|dirname|"
    r"awk|gawk|mawk|nawk|sed|cut|tr|sort|uniq|wc|xargs|tee|echo|printf|comm|join|paste|"
    r"vi|vim|nano|ed|emacs|"
    r"python|python2|python3|python3\.\d+|perl|ruby|node|php|lua|tclsh|expect|"
    r"bash|sh|zsh|ksh|dash|ash|env|export|unset|set|source|eval|exec|declare|"
    r"chmod|chown|chgrp|cp|mv|rm|ln|mkdir|rmdir|touch|dd|install|mktemp|shred|truncate|"
    r"getcap|setcap|capsh|getfacl|setfacl|lsattr|chattr|"
    r"ss|netstat|ip|ifconfig|arp|route|nc|ncat|netcat|socat|telnet|ping|"
    r"curl|wget|"
    r"redis-cli|mysql|mysqladmin|psql|mongo|mongosh|sqlite3|"
    r"ps|top|htop|pstree|lsof|fuser|pgrep|pkill|kill|nice|nohup|timeout|watch|"
    r"crontab|at|batch|systemctl|service|initctl|journalctl|loginctl|"
    r"mount|umount|findmnt|lsblk|blkid|df|du|"
    r"getent|groups|sudoedit|passwd|gpasswd|chsh|chfn|newgrp|login|useradd|usermod|"
    r"tar|gzip|gunzip|zcat|zip|unzip|bzip2|xz|cpio|ar|"
    r"gdb|strace|ltrace|nm|objdump|ldd|readelf|xxd|od|hexdump|base64|"
    r"nmap|ssh|scp|sftp|ssh-keygen|ssh-keyscan|rsync|"
    r"apt|apt-get|dpkg|yum|dnf|rpm|pip|pip3|gem|npm|make|gcc|cc|"
    r"date|sleep|history|alias|which|type|command|apropos|man|test|true|false|seq|yes|"
    r"docker|kubectl|crictl|podman|lxc"
    r")\b",
    re.IGNORECASE,
)

# Shell "signals": if a line carries any of these it is almost certainly a
# command rather than an English sentence.
_COMMAND_SIGNAL = re.compile(r"""[|;&<>$`*]|(?:^|\s)-{1,2}\w|=|['"]|\./|~/|/\w""")

# Leading wrappers (sudo/doas flags, env VAR=..., inline VAR=... assignments)
# that precede the real binary — stripped before inspecting the command head.
_LEADING_WRAPPERS = re.compile(
    r"^(?:(?:sudo|doas)(?:\s+-\w+)*\s+|env(?:\s+-\w+)*\s+(?:\w+=\S*\s+)*|\w+=\S*\s+)+",
    re.IGNORECASE,
)


def _looks_like_command(line: str) -> bool:
    """
    Heuristic acceptance for commands not covered by ``_SHELL_HEAD``.

    Accepts path invocations, bare single-token commands, and any binary-headed
    line that carries a shell signal (option, pipe, redirect, path, quote, …),
    while rejecting multi-word English prose that carries no such signal.
    """
    core = (_LEADING_WRAPPERS.sub("", line).strip() or line)
    if re.match(r"^[/~]|^\.{1,2}/", core):
        return True
    head_match = re.match(r"^([A-Za-z_][\w.+-]*)(.*)$", core, re.DOTALL)
    if not head_match:
        return False
    if not head_match.group(2).strip():
        return True
    return bool(_COMMAND_SIGNAL.search(line))


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
    if line.endswith(":") and not line.lower().startswith("sudo"):
        return False
    if _SHELL_HEAD.match(line):
        return True
    if line.startswith("!/"):
        return True
    return _looks_like_command(line)


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
