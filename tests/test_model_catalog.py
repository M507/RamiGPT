"""Tests for AI model catalog helpers."""

from __future__ import annotations

from ramigpt.ai.model_catalog import saved_model_for_provider
from ramigpt.config import Settings


def test_saved_model_for_provider():
    settings = Settings(
        ollama_model="qwen3:14b",
        openai_model="gpt-test",
        openwebui_model="llama3.1",
        cursor_model="composer-2.5",
    )
    assert saved_model_for_provider(settings, "ollama") == "qwen3:14b"
    assert saved_model_for_provider(settings, "openai") == "gpt-test"
    assert saved_model_for_provider(settings, "unknown") == ""
