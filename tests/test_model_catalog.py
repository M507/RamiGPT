"""Tests for AI model catalog helpers."""

from __future__ import annotations

from ramigpt.ai.model_catalog import saved_model_for_provider
from ramigpt.ai.providers.compat import openwebui_openai_base_url
from ramigpt.config import Settings


def test_openwebui_openai_base_url():
    assert openwebui_openai_base_url("http://10.10.10.82:8080") == (
        "http://10.10.10.82:8080/api/v1"
    )
    assert openwebui_openai_base_url("http://10.10.10.82:8080/") == (
        "http://10.10.10.82:8080/api/v1"
    )
    assert openwebui_openai_base_url("http://host:8080/api") == (
        "http://host:8080/api/v1"
    )
    assert openwebui_openai_base_url("http://host:8080/api/v1") == (
        "http://host:8080/api/v1"
    )


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
