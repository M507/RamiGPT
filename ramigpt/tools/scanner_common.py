"""Shared helpers for bundled enumeration tool runners."""

from __future__ import annotations

import re
from typing import Callable, Optional

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_URL_LINE_RE = re.compile(
    r"^\s*(?:https?://|www\.|ftp://|\[\+\]\s*https?://)",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://\S+")

# LinPEAS can emit hundreds of KB; cap what we inject into the model prompt.
DEFAULT_MAX_PROMPT_CHARS = 80_000


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text or "")


def sanitize_scanner_for_prompt(
    scanner_text: str,
    *,
    max_chars: int = DEFAULT_MAX_PROMPT_CHARS,
) -> str:
    """
    Strip ANSI escapes, drop standalone URL lines, and cap size for model context.
    """
    text = strip_ansi(scanner_text or "").strip()
    if not text:
        return text

    cleaned = []
    for line in text.splitlines():
        if _URL_LINE_RE.match(line):
            continue
        stripped = _URL_RE.sub("", line).rstrip()
        if stripped:
            cleaned.append(stripped)
    text = "\n".join(cleaned).strip()
    if len(text) <= max_chars:
        return text

    head = max_chars // 2
    tail = max_chars - head - 48
    if tail < 0:
        return text[:max_chars] + "\n…[truncated for prompt]…"
    omitted = len(text) - head - max(tail, 0)
    return (
        text[:head]
        + f"\n…[truncated {omitted} chars for prompt size]…\n"
        + text[-max(tail, 0) :]
    )


def append_sudo_l_enrichment(
    text: str,
    *,
    ssh_conn,
    password: str,
    sh_quote: Callable[[str], str],
    ssh_run: Callable[..., bytes],
    slog=None,
) -> str:
    """Append a plain sudo -l capture when the scanner misses NOPASSWD listings."""
    pw = sh_quote(password)
    try:
        probe_cmd = (
            f"echo {pw} | sudo -S -l 2>/dev/null; "
            "sudo -ln 2>/dev/null; echo __SUDO_L_DONE__"
        )
        pbuf = ssh_run(ssh_conn, probe_cmd, timeout=20, slog=slog)
        sudo_l = (pbuf or b"").decode("utf-8", errors="replace")
        sudo_l = sudo_l.split("__SUDO_L_DONE__")[0]
        lines = [
            ln
            for ln in sudo_l.splitlines()
            if ln.strip()
            and not ln.strip().startswith("$")
            and "sudo -S -l" not in ln
            and "sudo -ln" not in ln
        ]
        sudo_clean = "\n".join(lines).strip()
        if sudo_clean and (
            "may run" in sudo_clean.lower()
            or "NOPASSWD" in sudo_clean
            or "sudoers" in sudo_clean.lower()
            or "(root)" in sudo_clean
        ):
            return (
                text
                + "\n\n################ sudo -l (runner capture) ################\n\n"
                + sudo_clean
                + "\n"
            )
    except Exception as exc:  # noqa: BLE001
        if slog is not None:
            slog.warning(f"scanner: sudo -l enrichment skipped: {exc}")
    return text


def upload_and_run_shell_script(
    ssh_conn,
    *,
    local_script,
    remote_script: str,
    remote_out: str,
    run_cmd: str,
    ready_token: str,
    log_prefix: str,
    output_block_name: str,
    sh_quote: Callable[[str], str],
    ssh_run: Callable[..., bytes],
    password: str = "",
    slog=None,
    timeout: int = 300,
    enrich_sudo: bool = True,
    max_prompt_chars: Optional[int] = DEFAULT_MAX_PROMPT_CHARS,
) -> str:
    """
    Upload a local shell script, run ``run_cmd`` on the remote host, download output.
    """
    if not local_script.is_file():
        raise FileNotFoundError(f"{log_prefix}: script missing at {local_script}")

    if slog is not None:
        slog.info(f"{log_prefix}: uploading {local_script} → {remote_script}")
    ssh_conn.upload(str(local_script), remote_script)

    prep = ssh_run(
        ssh_conn,
        f"chmod +x {remote_script} && test -f {remote_script} && echo {ready_token}",
        timeout=30,
        slog=slog,
    )
    if ready_token.encode() not in (prep or b""):
        raise RuntimeError(
            f"{log_prefix}: upload failed on remote host (tail: {(prep or b'')[-400]!r})"
        )

    remote_cmd = (
        f"{{ {run_cmd}; }} > {remote_out} 2>&1; "
        f"echo __SCANNER_EXIT__:$?; wc -c {remote_out}"
    )
    if slog is not None:
        slog.info(f"{log_prefix}: starting remote scan")

    buf = ssh_run(ssh_conn, remote_cmd, timeout=max(60, int(timeout)), slog=slog)

    text = ""
    try:
        raw = ssh_conn.download_data(remote_out)
        if isinstance(raw, bytes):
            text = raw.decode("utf-8", errors="replace")
        else:
            text = str(raw or "")
    except Exception as exc:  # noqa: BLE001
        if slog is not None:
            slog.warning(f"{log_prefix}: download {remote_out} failed: {exc}")
        text = (buf or b"").decode("utf-8", errors="replace")

    text = (text or "").strip()
    if not text:
        raise RuntimeError(
            f"{log_prefix}: produced empty output. "
            f"Remote buffer tail: {(buf or b'')[-500]!r}"
        )

    if enrich_sudo and password:
        text = append_sudo_l_enrichment(
            text,
            ssh_conn=ssh_conn,
            password=password,
            sh_quote=sh_quote,
            ssh_run=ssh_run,
            slog=slog,
        )

    if slog is not None:
        slog.info(f"{log_prefix}: scan finished ({len(text)} chars)")
        slog.block(output_block_name, text[:20000])

    if max_prompt_chars is not None:
        return sanitize_scanner_for_prompt(text, max_chars=max_prompt_chars)
    return text
