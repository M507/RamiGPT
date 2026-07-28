"""Tests for benchmark AI model warmup."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ramigpt.ai.providers.ollama_provider import ollama_model_names_match
from ramigpt.ai.probe import PROVIDER_PROBE_MESSAGES
from ramigpt.benchmark.model_warmup import warmup_ai_model
from ramigpt.config import Settings


def test_ollama_model_names_match():
    assert ollama_model_names_match("qwen3:14b", "qwen3:14b")
    assert ollama_model_names_match("deepseek-r1:14b", "deepseek-r1:14b")
    assert ollama_model_names_match("qwen3:14b", "qwen3:latest") is False
    assert ollama_model_names_match("gpt-4o", "qwen3:14b") is False


def test_warmup_skips_when_already_warm():
    settings = Settings(ai_provider="ollama", ollama_model="qwen3:14b")
    result = warmup_ai_model(settings, last_warm=("ollama", "qwen3:14b"))
    assert result.ok is True
    assert result.skipped is True
    assert "skipped" in result.log_lines[0].lower()


@patch("ramigpt.benchmark.model_warmup.create_provider")
@patch("ramigpt.benchmark.model_warmup.list_ollama_running_models")
def test_warmup_ollama_probe_and_ps(mock_ps, mock_create):
    mock_ps.side_effect = [["qwen3:14b"], ["deepseek-r1:14b"]]
    provider = MagicMock()
    provider.create_completion.return_value = "ok"
    mock_create.return_value = provider

    settings = Settings(
        ai_provider="ollama",
        ollama_base_url="http://127.0.0.1:11434",
        ollama_model="deepseek-r1:14b",
    )
    result = warmup_ai_model(settings, last_warm=None)

    assert result.ok is True
    assert result.skipped is False
    assert result.ollama_verified is True
    assert result.probe_seconds is not None
    provider.create_completion.assert_called_once_with(PROVIDER_PROBE_MESSAGES)
    assert any("Ollama ps before warmup" in line for line in result.log_lines)
    assert any("warmup OK" in line for line in result.log_lines)


@patch("ramigpt.benchmark.model_warmup.create_provider")
@patch("ramigpt.benchmark.model_warmup.list_ollama_running_models")
def test_warmup_failure_is_logged(mock_ps, mock_create):
    mock_ps.return_value = []
    mock_create.side_effect = RuntimeError("connection refused")

    settings = Settings(ai_provider="openai", openai_api_key="sk-test", openai_model="gpt-test")
    result = warmup_ai_model(settings, last_warm=None)

    assert result.ok is False
    assert "FAILED" in result.log_lines[-1]
