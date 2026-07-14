"""Domain models and privilege-escalation logic."""

from .prompt import PrivEscPrompt, normalize_ai_command
from .root_detection import diagnose_root, got_root

__all__ = ["PrivEscPrompt", "normalize_ai_command", "got_root", "diagnose_root"]
