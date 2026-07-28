"""Tests for Open WebUI provider and completion validation."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from ramigpt.ai.providers.compat import require_chat_completion_text
from ramigpt.ai.providers.openwebui_provider import OpenWebUIProvider
from ramigpt.config import Settings


class RequireChatCompletionTextTests(unittest.TestCase):
    def test_null_completion_raises(self):
        with self.assertRaisesRegex(RuntimeError, "empty HTTP body"):
            require_chat_completion_text(
                None,
                provider="openwebui",
                model="openai/gpt-5:latest",
                base_url="http://host:8080/api/v1",
            )

    def test_missing_choices_raises(self):
        with self.assertRaisesRegex(RuntimeError, "no choices"):
            require_chat_completion_text(
                SimpleNamespace(choices=[]),
                provider="openwebui",
                model="test",
                base_url="http://host:8080/api/v1",
            )

    def test_empty_message_raises(self):
        completion = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=""))]
        )
        with self.assertRaisesRegex(RuntimeError, "empty message"):
            require_chat_completion_text(
                completion,
                provider="openwebui",
                model="test",
                base_url="http://host:8080/api/v1",
            )

    def test_valid_message_returns_text(self):
        completion = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="sudo -l"))]
        )
        self.assertEqual(
            require_chat_completion_text(
                completion,
                provider="openwebui",
                model="test",
                base_url="http://host:8080/api/v1",
            ),
            "sudo -l",
        )


class OpenWebUIProviderTests(unittest.TestCase):
    def test_uses_api_v1_base_url(self):
        settings = Settings(
            openwebui_base_url="http://10.10.10.82:8080",
            openwebui_model="qwen3:14b",
        )
        provider = OpenWebUIProvider(settings, client=mock.Mock())
        self.assertEqual(provider._base_url, "http://10.10.10.82:8080/api/v1")

    def test_null_sdk_response_raises(self):
        class FakeCompletions:
            def create(self, *args, **kwargs):
                return None

        fake_client = SimpleNamespace(
            chat=SimpleNamespace(completions=FakeCompletions())
        )
        settings = Settings(
            openwebui_base_url="http://10.10.10.82:8080",
            openwebui_model="openai/gpt-5:latest",
        )
        provider = OpenWebUIProvider(settings, client=fake_client)
        with self.assertRaisesRegex(RuntimeError, "empty HTTP body"):
            provider.create_completion(
                [
                    {"role": "system", "content": "test"},
                    {"role": "user", "content": "id"},
                ]
            )


if __name__ == "__main__":
    unittest.main()
