"""High-level command execution entry points for Upgraded Session v2."""

from __future__ import annotations

from typing import Any, Optional

from ramigpt.config.settings import get_settings
from ramigpt.session_v2.extraction import extract_command_from_response
from ramigpt.session_v2.interactive import InteractiveSessionDriver
from ramigpt.session_v2.normalize import prepare_command
from ramigpt.session_v2.types import CommandRunResult, ShellBridge


def is_enabled() -> bool:
    """Return True when Upgraded Session v2 is active."""
    return bool(get_settings().upgraded_session_v2)


def extract_command(raw_response: str) -> Optional[str]:
    return extract_command_from_response(raw_response)


def normalize_command(command: Optional[str]) -> Optional[str]:
    return prepare_command(command)


def execute_command(
    shell: Any,
    command: str,
    *,
    bridge: ShellBridge,
    hostname: str,
    password: str,
    timeout: float = 12.0,
) -> CommandRunResult:
    """Send one command and drive the PTY until a stable outcome."""
    driver = InteractiveSessionDriver(
        bridge=bridge,
        hostname=hostname,
        password=password,
        timeout=timeout,
    )
    return driver.execute(shell, command)


def process_ai_response(raw_response: str) -> Optional[str]:
    """Extract and normalize a model response into an executable command."""
    extracted = extract_command_from_response(raw_response)
    return prepare_command(extracted)
