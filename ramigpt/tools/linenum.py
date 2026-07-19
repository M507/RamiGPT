"""LinEnum upload, remote execution, and prompt sanitization."""

from __future__ import annotations

from typing import Callable

from ramigpt.paths import LINENUM_SCRIPT
from ramigpt.tools.scanner_common import (
    DEFAULT_MAX_PROMPT_CHARS,
    sanitize_scanner_for_prompt,
    upload_and_run_shell_script,
)

__all__ = [
    "DEFAULT_MAX_PROMPT_CHARS",
    "sanitize_linenum_for_prompt",
    "upload_and_run_linenum",
]


def sanitize_linenum_for_prompt(linenum_text: str, *, max_chars: int = DEFAULT_MAX_PROMPT_CHARS) -> str:
    """Prepare LinEnum output for the model."""
    return sanitize_scanner_for_prompt(linenum_text, max_chars=max_chars)


def upload_and_run_linenum(
    ssh_conn,
    *,
    password: str,
    sh_quote: Callable[[str], str],
    ssh_run: Callable[..., bytes],
    slog=None,
    timeout: int = 300,
) -> str:
    """
    Upload tools/linenum/LinEnum.sh to the remote host, run a thorough scan,
    and return captured stdout (also written remotely to /tmp/linenum.txt).
    """
    # Do not pass -s: LinEnum prompts interactively for the password.
    run_cmd = "bash /tmp/LinEnum.sh -t"
    return upload_and_run_shell_script(
        ssh_conn,
        local_script=LINENUM_SCRIPT,
        remote_script="/tmp/LinEnum.sh",
        remote_out="/tmp/linenum.txt",
        run_cmd=run_cmd,
        ready_token="LINENUM_READY",
        log_prefix="linenum",
        output_block_name="LINENUM_OUTPUT",
        sh_quote=sh_quote,
        ssh_run=ssh_run,
        password=password,
        slog=slog,
        timeout=timeout,
        enrich_sudo=True,
    )
