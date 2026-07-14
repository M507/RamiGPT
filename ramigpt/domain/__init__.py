"""Domain models and privilege-escalation logic."""

from .prompt import PrivEscPrompt
from .root_detection import got_root

__all__ = ["PrivEscPrompt", "got_root"]
