"""Tests for the Cursor Cloud Agents provider."""

from __future__ import annotations

import json
import unittest
from unittest import mock

from ramigpt.ai.providers.cursor_provider import (
    CursorProvider,
    _build_prompt_text,
    _sort_cursor_models,
    list_cursor_models,
)
from ramigpt.config import Settings


def _fake_http_response(payload: dict) -> mock.MagicMock:
    resp = mock.MagicMock()
    resp.read.return_value = json.dumps(payload).encode("utf-8")
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


class BuildPromptTextTests(unittest.TestCase):
    def test_combines_system_and_user_messages(self):
        messages = [
            {"role": "system", "content": "You are an experienced pentester."},
            {"role": "user", "content": "What should I try next?"},
        ]
        text = _build_prompt_text(messages)
        self.assertIn("You are an experienced pentester.", text)
        self.assertIn("What should I try next?", text)

    def test_skips_empty_messages(self):
        messages = [{"role": "system", "content": ""}, {"role": "user", "content": "hi"}]
        self.assertEqual(_build_prompt_text(messages), "hi")


class CursorProviderTests(unittest.TestCase):
    def _settings(self, **overrides) -> Settings:
        base = Settings(ai_provider="cursor", cursor_api_key="test-key", cursor_model="composer-2.5")
        for key, value in overrides.items():
            setattr(base, key, value)
        return base

    def test_requires_api_key(self):
        with self.assertRaises(ValueError):
            CursorProvider(Settings(ai_provider="cursor", cursor_api_key=""))

    @mock.patch("ramigpt.ai.providers.cursor_provider.time.sleep", return_value=None)
    @mock.patch("ramigpt.ai.providers.cursor_provider.urllib.request.urlopen")
    def test_create_completion_polls_until_finished_and_archives(self, mock_urlopen, _mock_sleep):
        create_resp = _fake_http_response(
            {
                "agent": {"id": "bc-1"},
                "run": {"id": "run-1", "status": "CREATING"},
            }
        )
        running_resp = _fake_http_response({"status": "RUNNING"})
        finished_resp = _fake_http_response({"status": "FINISHED", "result": "nmap -sV target"})
        usage_resp = _fake_http_response(
            {"totalUsage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15}}
        )
        archive_resp = _fake_http_response({"id": "bc-1"})

        mock_urlopen.side_effect = [
            create_resp,
            running_resp,
            finished_resp,
            usage_resp,
            archive_resp,
        ]

        provider = CursorProvider(self._settings())
        result = provider.create_completion(
            [
                {"role": "system", "content": "You are an experienced pentester."},
                {"role": "user", "content": "What next?"},
            ]
        )

        self.assertEqual(result, "nmap -sV target")
        self.assertEqual(
            provider.last_usage,
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

        # 5 calls: create agent, 2 polls, usage fetch, archive.
        self.assertEqual(mock_urlopen.call_count, 5)
        archive_request = mock_urlopen.call_args_list[-1][0][0]
        self.assertIn("/archive", archive_request.full_url)

    @mock.patch("ramigpt.ai.providers.cursor_provider.urllib.request.urlopen")
    def test_create_completion_raises_on_missing_ids(self, mock_urlopen):
        mock_urlopen.return_value = _fake_http_response({"agent": {}, "run": {}})
        provider = CursorProvider(self._settings())
        with self.assertRaises(RuntimeError):
            provider.create_completion([{"role": "user", "content": "hi"}])

    @mock.patch("ramigpt.ai.providers.cursor_provider.time.sleep", return_value=None)
    @mock.patch("ramigpt.ai.providers.cursor_provider.urllib.request.urlopen")
    def test_create_completion_raises_on_error_status(self, mock_urlopen, _mock_sleep):
        create_resp = _fake_http_response({"agent": {"id": "bc-1"}, "run": {"id": "run-1"}})
        error_resp = _fake_http_response({"status": "ERROR", "result": "boom"})
        archive_resp = _fake_http_response({"id": "bc-1"})
        mock_urlopen.side_effect = [create_resp, error_resp, archive_resp]

        provider = CursorProvider(self._settings())
        with self.assertRaises(RuntimeError):
            provider.create_completion([{"role": "user", "content": "hi"}])


class ListCursorModelsTests(unittest.TestCase):
    def test_requires_api_key(self):
        with self.assertRaises(ValueError):
            list_cursor_models("")

    @mock.patch("ramigpt.ai.providers.cursor_provider.urllib.request.urlopen")
    def test_parses_model_ids(self, mock_urlopen):
        mock_urlopen.return_value = _fake_http_response(
            {
                "items": [
                    {"id": "composer-2.5", "displayName": "Composer 2.5"},
                    {"id": "claude-sonnet-4-6", "displayName": "Sonnet 4.6"},
                ]
            }
        )
        models = list_cursor_models("test-key")
        # Costly → cheap: Sonnet before Composer; Auto always last.
        self.assertEqual(models, ["claude-sonnet-4-6", "composer-2.5", "default"])

    def test_sorts_models_costly_to_cheap(self):
        sorted_models = _sort_cursor_models(
            [
                {"id": "default", "displayName": "Auto"},
                {"id": "gemini-3-flash", "displayName": "Gemini 3 Flash"},
                {"id": "composer-2.5", "displayName": "Composer 2.5"},
                {"id": "claude-opus-4-8", "displayName": "Opus 4.8"},
                {"id": "claude-haiku-4-5", "displayName": "Haiku 4.5"},
                {"id": "gpt-5.4-mini", "displayName": "GPT-5.4 Mini"},
            ]
        )
        self.assertEqual(
            [item["id"] for item in sorted_models],
            [
                "claude-opus-4-8",
                "composer-2.5",
                "gpt-5.4-mini",
                "claude-haiku-4-5",
                "gemini-3-flash",
                "default",
            ],
        )

    @mock.patch("ramigpt.ai.providers.cursor_provider.urllib.request.urlopen")
    def test_always_includes_auto_option(self, mock_urlopen):
        mock_urlopen.return_value = _fake_http_response(
            {
                "items": [
                    {"id": "composer-2.5", "displayName": "Composer 2.5"},
                ]
            }
        )
        from ramigpt.ai.providers.cursor_provider import list_cursor_model_details

        details = list_cursor_model_details("test-key")
        ids = [item["id"] for item in details]
        self.assertIn("default", ids)
        self.assertEqual(ids[-1], "default")
        auto = next(item for item in details if item["id"] == "default")
        self.assertIn("Auto", auto["displayName"])
        self.assertIn("cheap", auto["displayName"].lower())

    def test_remaps_obsolete_composer_2_id(self):
        provider = CursorProvider(
            Settings(ai_provider="cursor", cursor_api_key="test-key", cursor_model="composer-2")
        )
        self.assertEqual(provider._model, "composer-2.5")


if __name__ == "__main__":
    unittest.main()
