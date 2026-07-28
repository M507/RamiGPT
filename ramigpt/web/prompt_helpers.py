"""AI prompt construction and BeRoot sanitization."""

from __future__ import annotations

import re

from ramigpt.ai.openwebui_prompt import sanitize_for_openwebui
from ramigpt.config import get_role_objective, get_rotated_role_objective, get_settings
from ramigpt.domain import PrivEscPrompt
from ramigpt.utils import debug_logger
from ramigpt.utils.session_logging import load_shell_command_history
from ramigpt.web.state import _prompt_history_stash

def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text or "")


def sanitize_beroot_for_prompt(beroot_text: str) -> str:
    """
    Prepare BeRoot output for the model: strip ANSI, drop GTFOBins exploit
    payloads and kernel-exploit listings that cause Open WebUI external models to
    return null, and remove reference URLs that waste prompt space.
    """
    text = _strip_ansi(beroot_text or "").strip()
    if not text:
        return text
    return sanitize_for_openwebui(text)


def sanitize_prompt_for_openwebui(prompt: str) -> str:
    """Apply Open WebUI-safe filtering to a full model prompt."""
    return sanitize_for_openwebui(prompt or "")
def _max_ai_requests() -> int:
    return get_settings().openai_max_num_of_reqs


def _debug_enabled() -> int:
    return get_settings().debug


def _generate_ai_prompt(priv_esc) -> str:
    settings = get_settings()
    role_objective = get_role_objective(settings.role_objective)
    if settings.rotate_role_objectives:
        rotation_base = getattr(priv_esc, "_role_rotation_base", None)
        if rotation_base != settings.role_objective:
            priv_esc._role_rotation_base = settings.role_objective
            priv_esc._role_rotation_offset = 0
        offset = getattr(priv_esc, "_role_rotation_offset", 0)
        _, role_objective = get_rotated_role_objective(
            settings.role_objective,
            offset,
        )
        priv_esc._role_rotation_offset = offset + 1
    else:
        priv_esc._role_rotation_base = settings.role_objective
        priv_esc._role_rotation_offset = 0
    prompt = priv_esc.generate_prompt(
        include_history_outputs=bool(settings.history_include_outputs),
        history_output_edge_count=settings.history_output_edge_count,
        role_objective=role_objective,
    )
    if settings.ai_provider == "openwebui":
        prompt = sanitize_prompt_for_openwebui(prompt)
    return prompt
def _seed_prompt_history(session_id, priv_esc) -> int:
    """
    Restore prior command history into a PrivEscPrompt.

    Prefers an in-memory stash from the last disconnect, then fills gaps from
    SHELL_IO events on disk (covers app restart / stopped Full AI loops).
    """
    if priv_esc is None:
        return 0
    added = 0
    stashed = _prompt_history_stash.pop(session_id, None) or []
    if stashed:
        added += int(priv_esc.merge_history_entries(stashed) or 0)
    try:
        from_logs = load_shell_command_history(session_id)
    except Exception:  # noqa: BLE001
        from_logs = []
    if from_logs:
        added += int(priv_esc.merge_history_entries(from_logs) or 0)
    return added


def _make_priv_esc_prompt(session_id, username, password, system, target_user):
    """Create a PrivEscPrompt and reseed command history for this session."""
    priv = PrivEscPrompt(username, password, system, target_user)
    seeded = _seed_prompt_history(session_id, priv)
    if seeded:
        debug_logger.info(
            f"prompt.history_seeded session_id={session_id!r} entries={len(priv.history)}"
        )
    return priv
