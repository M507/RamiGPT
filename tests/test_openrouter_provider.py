"""Tests for OpenRouter provider helpers and completion handling."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from ramigpt.ai.providers.openrouter_provider import (
    DEFAULT_BASE_URL,
    OpenRouterProvider,
    openrouter_base_url,
)
from ramigpt.config import Settings


class OpenRouterBaseUrlTests(unittest.TestCase):
    def test_default_and_suffix(self):
        self.assertEqual(openrouter_base_url(""), DEFAULT_BASE_URL)
        self.assertEqual(openrouter_base_url("https://openrouter.ai/api"), DEFAULT_BASE_URL)
        self.assertEqual(
            openrouter_base_url("https://openrouter.ai/api/v1"),
            DEFAULT_BASE_URL,
        )
        self.assertEqual(
            openrouter_base_url("https://proxy.example"),
            "https://proxy.example/api/v1",
        )


class OpenRouterProviderTests(unittest.TestCase):
    def test_requires_api_key(self):
        with self.assertRaisesRegex(ValueError, "OPENROUTER_API_KEY"):
            OpenRouterProvider(Settings(openrouter_api_key=""))

    def test_create_completion_returns_message_text(self):
        class FakeChat:
            def send(self, **kwargs):
                self.kwargs = kwargs
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content="sudo -l", reasoning=None)
                        )
                    ],
                    usage=SimpleNamespace(
                        prompt_tokens=10,
                        completion_tokens=4,
                        total_tokens=14,
                    ),
                )

        fake_client = SimpleNamespace(chat=FakeChat())
        settings = Settings(
            openrouter_api_key="sk-or-test",
            openrouter_model="openai/gpt-4o-mini",
        )
        provider = OpenRouterProvider(settings, client=fake_client)
        reply = provider.create_completion(
            [
                {"role": "system", "content": "test"},
                {"role": "user", "content": "id"},
            ]
        )
        self.assertEqual(reply, "sudo -l")
        self.assertEqual(provider.last_usage["total_tokens"], 14)
        self.assertEqual(fake_client.chat.kwargs["model"], "openai/gpt-4o-mini")
        self.assertFalse(fake_client.chat.kwargs["stream"])

    def test_empty_message_raises(self):
        class FakeChat:
            def send(self, **kwargs):
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content="", reasoning=None)
                        )
                    ],
                    usage=None,
                )

        fake_client = SimpleNamespace(chat=FakeChat())
        provider = OpenRouterProvider(
            Settings(openrouter_api_key="sk-or-test", openrouter_model="test"),
            client=fake_client,
        )
        with self.assertRaisesRegex(RuntimeError, "empty message"):
            provider.create_completion([{"role": "user", "content": "hi"}])

    def test_factory_selects_openrouter(self):
        from ramigpt.ai.factory import create_provider
        from ramigpt.ai.request_queue import QueuedAIProvider

        with mock.patch(
            "ramigpt.ai.providers.openrouter_provider.OpenRouter"
        ) as mock_sdk:
            mock_sdk.return_value = SimpleNamespace(chat=SimpleNamespace())
            provider = create_provider(
                Settings(
                    ai_provider="openrouter",
                    openrouter_api_key="sk-or-test",
                    openrouter_model="openai/gpt-4o-mini",
                )
            )
        self.assertIsInstance(provider, QueuedAIProvider)
        self.assertEqual(provider.name, "openrouter")


if __name__ == "__main__":
    unittest.main()
