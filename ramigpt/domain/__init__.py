"""Domain models and privilege-escalation logic."""

from .prompt import PrivEscPrompt
from .root_detection import diagnose_root, got_root

__all__ = ["PrivEscPrompt", "got_root", "diagnose_root"]
