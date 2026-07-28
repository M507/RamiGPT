"""Resolve AI commands for Full AI — v2 or legacy path."""

from __future__ import annotations

from typing import Any, Optional

from ramigpt.domain.prompt import normalize_ai_command
from ramigpt.session_v2.extraction import extract_command_from_response
from ramigpt.session_v2.normalize import prepare_command
from ramigpt.session_v2.runner import is_enabled
from ramigpt.utils import remove_matching_quotes


def resolve_ai_command(raw_response: str, priv_esc: Any) -> Optional[str]:
    """
    Convert a model response into one executable shell command.

    Uses Upgraded Session v2 extraction when enabled; otherwise falls back to
    the legacy ``PrivEscPrompt.filter_output`` pipeline.
    """
    if is_enabled():
        extracted = extract_command_from_response(raw_response)
        return prepare_command(extracted)

    trimmed = priv_esc.filter_output(raw_response)
    return normalize_ai_command(remove_matching_quotes(trimmed))
