"""High-level AI completion helpers used by the application."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Union

from ramigpt.ai.base import AIProvider, ChatMessage
from ramigpt.ai.factory import create_provider


def get_answer(
    system_or_client: Union[str, AIProvider],
    prompt_or_system: str,
    prompt: Optional[str] = None,
) -> str:
    """
    Ask the configured AI provider for a completion.

    Preferred::
        get_answer(system, prompt)

    Legacy (still supported)::
        get_answer(client, system, prompt)
    """
    if prompt is None:
        # get_answer(system, prompt)
        if not isinstance(system_or_client, str):
            raise TypeError("get_answer(system, prompt) expects system as a string")
        provider = create_provider()
        system = system_or_client
        user_prompt = prompt_or_system
    else:
        # get_answer(client, system, prompt)
        provider = system_or_client if isinstance(system_or_client, AIProvider) else create_provider()
        system = prompt_or_system
        user_prompt = prompt

    messages: List[ChatMessage] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]
    return provider.create_completion(messages)


def get_answer_with_usage(
    system: str, prompt: str
) -> Tuple[str, Optional[Dict[str, int]]]:
    """
    Like ``get_answer(system, prompt)`` but also returns token usage
    (``{"prompt_tokens", "completion_tokens", "total_tokens"}``) when the
    provider reports it, or ``None`` otherwise.
    """
    provider = create_provider()
    messages: List[ChatMessage] = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    text = provider.create_completion(messages)
    usage = getattr(provider, "last_usage", None)
    return text, usage


def complete(messages: List[ChatMessage], provider: Optional[AIProvider] = None) -> str:
    return (provider or create_provider()).create_completion(messages)
