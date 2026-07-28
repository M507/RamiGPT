"""LinPEAS upload, remote execution, and prompt sanitization."""

from __future__ import annotations

from typing import Callable

from ramigpt.paths import LINPEAS_SCRIPT
from ramigpt.tools.scanner_common import (
    DEFAULT_MAX_PROMPT_CHARS,
    sanitize_scanner_for_prompt,
    upload_and_run_shell_script,
)

__all__ = [
    "DEFAULT_MAX_PROMPT_CHARS",
    "sanitize_linpeas_for_prompt",
    "upload_and_run_linpeas",
]


def sanitize_linpeas_for_prompt(linpeas_text: str, *, max_chars: int = DEFAULT_MAX_PROMPT_CHARS) -> str:
    """Prepare LinPEAS output for the model (ANSI strip, URL trim, size cap)."""
    return sanitize_scanner_for_prompt(linpeas_text, max_chars=max_chars)


def upload_and_run_linpeas(
    ssh_conn,
    *,
    password: str,
    sh_quote: Callable[[str], str],
    ssh_run: Callable[..., bytes],
    slog=None,
    timeout: int = 600,
) -> str:
    """
    Upload tools/linpeas/linpeas.sh, run in default fast/stealth mode with ``-P``
    for authenticated sudo checks, and return sanitized output.
    """
    pw = sh_quote(password)
    # -q: no banner; -s: superfast; -n: skip external hostname/leak lookups.
    run_cmd = f"bash /tmp/linpeas.sh -P {pw} -q -s -n"
    return upload_and_run_shell_script(
        ssh_conn,
        local_script=LINPEAS_SCRIPT,
        remote_script="/tmp/linpeas.sh",
        remote_out="/tmp/linpeas.txt",
        run_cmd=run_cmd,
        ready_token="LINPEAS_READY",
        log_prefix="linpeas",
        output_block_name="LINPEAS_OUTPUT",
        sh_quote=sh_quote,
        ssh_run=ssh_run,
        password=password,
        slog=slog,
        timeout=timeout,
        enrich_sudo=True,
    )
