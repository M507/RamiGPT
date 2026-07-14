"""Root-shell detection for many Linux / Unix prompt and identity shapes."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Pattern


def _escape_hostname(hostname: str) -> str:
    return re.escape(hostname.strip()) if hostname else ""


@lru_cache(maxsize=64)
def get_GOT_ROOT_REGEXPs(hostname: str = "") -> List[Pattern[str]]:
    """
    Regex library used by got_root().

    Prefer anchored prompt / identity lines. Patterns are applied with fullmatch
    first; search is only accepted for safe root-looking candidates.
    """
    host = _escape_hostname(hostname)
    patterns: List[str] = [
        r"^#\s*$",
        r"^(?:bash|sh|zsh|ksh|dash)-[0-9]+(?:\.[0-9]+)?#\s*$",
        r"^uid=0\(root\)(?:\s+gid=0\(root\))?.*$",
        r"^uid=0\(root\)\s+.*$",
        r"^euid=0\(root\).*$",
        r"^root$",
        r"^uid=0$",
    ]

    if host:
        patterns.extend(
            [
                rf"^root@{host}:.*#\s*$",
                rf"^root@{host}:.*#\s*",
                rf"^\(?root@{host}\)?\s*#\s*$",
            ]
        )

    patterns.extend(
        [
            r"^root@[A-Za-z0-9._+\-]+(?:\.[A-Za-z0-9._\-]+)*:[^\n]*#\s*$",
            r"^root@[A-Za-z0-9._+\-]+\s*#\s*$",
            r"^\[root@[^\]]+\]#\s*$",
            r"^root@[^:\s]+#\s*$",
            r"^(?:localhost|[A-Za-z0-9._\-]+):[~/\w.\-]*#\s*$",
            r"(?i)^you are root\b.*$",
            r"(?i)^effective (?:uid|user)\s*[:=]\s*0\b.*$",
            r"(?i)^euid\s*[:=]\s*0\b.*$",
            r"^root:x:0:0:.*$",
            r"^root@[A-Za-z0-9._\-]+(?:\.[A-Za-z0-9._\-]+)*/?#\s*$",
        ]
    )

    compiled: List[Pattern[str]] = []
    for expr in patterns:
        try:
            compiled.append(re.compile(expr, re.MULTILINE))
        except re.error:
            continue
    return compiled


def _iter_candidates(output: str) -> Iterable[str]:
    text = output.replace("\r\n", "\n").replace("\r", "\n")
    yield text.strip()
    for line in text.splitlines():
        raw = line.rstrip()
        yield raw
        stripped = raw.strip()
        if stripped != raw:
            yield stripped
        no_ansi = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", stripped)
        if no_ansi and no_ansi != stripped:
            yield no_ansi


def diagnose_root(hostname: Optional[str], output: Optional[str]) -> Dict[str, Any]:
    """
    Like got_root(), but returns a diagnosis for session logs:

      {"got_root": bool, "reason": str, "matched": ..., "checked": [...]}
    """
    host = (hostname or "").strip()
    checked: List[str] = []
    if output is None:
        return {"got_root": False, "reason": "output is None", "hostname": host, "checked": checked}
    text = str(output)
    if not text.strip():
        return {"got_root": False, "reason": "output empty/whitespace", "hostname": host, "checked": checked}

    if "uid=0(root)" in text or "euid=0(root)" in text:
        return {
            "got_root": True,
            "reason": "blob contains uid=0(root) or euid=0(root)",
            "hostname": host,
            "matched": "uid=0(root)",
            "checked": checked,
        }
    checked.append("uid=0(root) substring")

    if re.search(r"\buid=0\b", text) and re.search(r"\broot\b", text):
        return {
            "got_root": True,
            "reason": "blob contains uid=0 and root tokens",
            "hostname": host,
            "matched": "uid=0+root",
            "checked": checked,
        }
    checked.append("uid=0 + root tokens")

    if host and f"root@{host}:" in text:
        return {
            "got_root": True,
            "reason": f"blob contains root@{host}:",
            "hostname": host,
            "matched": f"root@{host}:",
            "checked": checked,
        }
    if host:
        checked.append(f"root@{host}: substring")

    if host and re.search(rf"root@{re.escape(host)}\b.*#", text):
        return {
            "got_root": True,
            "reason": f"regex root@{host}…# matched in blob",
            "hostname": host,
            "matched": rf"root@{host}\\b.*#",
            "checked": checked,
        }

    patterns = get_GOT_ROOT_REGEXPs(host)
    candidates = list(_iter_candidates(text))
    for candidate in candidates:
        if not candidate:
            continue
        stripped = candidate.strip()
        if stripped in {"#", "root"}:
            return {
                "got_root": True,
                "reason": f"candidate is exact {stripped!r}",
                "hostname": host,
                "matched": stripped,
                "candidate": candidate,
                "checked": checked,
            }
        for pattern in patterns:
            if pattern.fullmatch(candidate) or pattern.fullmatch(stripped):
                return {
                    "got_root": True,
                    "reason": "regex fullmatch",
                    "hostname": host,
                    "matched": pattern.pattern,
                    "candidate": candidate,
                    "checked": checked,
                }
            matched = pattern.search(candidate)
            if not matched:
                continue
            if (
                stripped.endswith("#")
                or "uid=0" in stripped
                or stripped.startswith("root@")
                or stripped.lower().startswith("you are root")
                or stripped.lower().startswith("effective")
            ):
                return {
                    "got_root": True,
                    "reason": "regex search on root-looking candidate",
                    "hostname": host,
                    "matched": pattern.pattern,
                    "candidate": candidate,
                    "checked": checked,
                }

    preview_lines = [c for c in candidates if c][:12]
    return {
        "got_root": False,
        "reason": "no root markers / prompts matched",
        "hostname": host,
        "checked": checked + [f"patterns={len(patterns)}", f"candidates={len(candidates)}"],
        "candidate_preview": preview_lines,
        "output_tail": text[-400:],
    }


def got_root(hostname: Optional[str], output: Optional[str]) -> bool:
    """Return True if shell output indicates an effective root shell / uid 0."""
    return bool(diagnose_root(hostname, output).get("got_root"))


if __name__ == "__main__":
    samples = [
        ("pehost", "root@pehost:/home/lowpriv# "),
        ("pehost", "# "),
        ("pehost", "bash-5.1# "),
        ("bench-vim", "uid=0(root) gid=0(root) groups=0(root)"),
        ("bench-awk", "root@bench-awk:/#"),
        ("x", "[root@box]# "),
        ("x", "zeus@host:~$ "),
    ]
    for host, sample in samples:
        print(host, repr(sample), "->", got_root(host, sample))
