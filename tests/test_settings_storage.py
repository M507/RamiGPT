"""Tests for JSON-backed AI settings and .env-backed secrets."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ramigpt.config import settings as settings_module
from ramigpt.config.settings import Settings, SettingsManager


class SettingsStorageTests(unittest.TestCase):
    def test_json_choices_override_environment_without_loading_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = Path(tmp) / "ai_settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "ai_provider": "cursor",
                        "cursor_model": "claude-4.6-sonnet-thinking",
                        "history_include_outputs": 1,
                        "history_output_edge_count": 7,
                        "role_objective": "Enumeration-First Pentester",
                        "rotate_role_objectives": 1,
                        "openai_api_key": "must-not-load-from-json",
                    }
                )
            )
            environment = Settings(
                ai_provider="ollama",
                openai_api_key="env-secret",
                cursor_api_key="cursor-env-secret",
            )

            with mock.patch.object(
                settings_module, "AI_SETTINGS_PATH", settings_path
            ), mock.patch.object(
                settings_module,
                "_load_settings_from_env",
                return_value=environment,
            ):
                manager = SettingsManager()

            self.assertEqual(manager.settings.ai_provider, "cursor")
            self.assertEqual(
                manager.settings.cursor_model,
                "claude-4.6-sonnet-thinking",
            )
            self.assertEqual(manager.settings.openai_api_key, "env-secret")
            self.assertEqual(manager.settings.cursor_api_key, "cursor-env-secret")
            self.assertEqual(manager.settings.history_include_outputs, 1)
            self.assertEqual(manager.settings.history_output_edge_count, 7)
            self.assertEqual(
                manager.settings.role_objective,
                "Enumeration-First Pentester",
            )
            self.assertEqual(manager.settings.rotate_role_objectives, 1)

    def test_save_writes_choices_to_json_and_only_secrets_to_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings_path = root / "data" / "ai_settings.json"
            env_path = root / ".env"
            env_path.write_text(
                "# deployment defaults\n"
                "AI_PROVIDER=ollama\n"
                "OPENAI_API_KEY=old-key\n"
            )
            environment = Settings(
                ai_provider="ollama",
                openai_api_key="old-key",
                cursor_api_key="old-cursor-key",
            )

            with mock.patch.object(
                settings_module, "AI_SETTINGS_PATH", settings_path
            ), mock.patch.object(
                settings_module, "ENV_PATH", env_path
            ), mock.patch.object(
                settings_module,
                "_load_settings_from_env",
                return_value=environment,
            ):
                manager = SettingsManager()
                manager.update(
                    {
                        "ai_provider": "cursor",
                        "cursor_model": "composer-2.5",
                        "cursor_api_key": "new-cursor-key",
                        "history_include_outputs": 1,
                        "history_output_edge_count": 0,
                        "role_objective": "Direct Privilege Escalation Operator",
                        "rotate_role_objectives": 1,
                    },
                    persist=True,
                )

            payload = json.loads(settings_path.read_text())
            self.assertEqual(payload["ai_provider"], "cursor")
            self.assertEqual(payload["cursor_model"], "composer-2.5")
            self.assertEqual(payload["history_include_outputs"], 1)
            self.assertEqual(payload["history_output_edge_count"], 0)
            self.assertEqual(
                payload["role_objective"],
                "Direct Privilege Escalation Operator",
            )
            self.assertEqual(payload["rotate_role_objectives"], 1)
            self.assertNotIn("cursor_api_key", payload)
            self.assertNotIn("openai_api_key", payload)

            env_text = env_path.read_text()
            self.assertIn("# deployment defaults", env_text)
            self.assertIn("AI_PROVIDER=ollama", env_text)
            self.assertIn("CURSOR_API_KEY=new-cursor-key", env_text)
            self.assertNotIn("CURSOR_MODEL=", env_text)

    def test_role_objectives_load_names_and_values_from_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            roles_path = Path(tmp) / "role_objectives.json"
            roles_path.write_text(
                json.dumps(
                    {
                        "Custom operator": (
                            "Act as {username} on {system}; reach {target_user}."
                        )
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch.object(
                settings_module, "ROLE_OBJECTIVES_PATH", roles_path
            ):
                roles = settings_module.load_role_objectives()
                public = Settings(role_objective="Custom operator").to_public_dict()

            self.assertEqual(
                roles["Custom operator"],
                "Act as {username} on {system}; reach {target_user}.",
            )
            self.assertEqual(public["role_objective"], "Custom operator")
            self.assertEqual(public["role_objective_options"], ["Custom operator"])

    def test_rotated_role_objective_starts_at_selection_and_wraps(self):
        with tempfile.TemporaryDirectory() as tmp:
            roles_path = Path(tmp) / "role_objectives.json"
            roles_path.write_text(
                json.dumps({"One": "first", "Two": "second", "Three": "third"}),
                encoding="utf-8",
            )

            with mock.patch.object(
                settings_module, "ROLE_OBJECTIVES_PATH", roles_path
            ):
                selected = [
                    settings_module.get_rotated_role_objective("Two", offset)
                    for offset in range(4)
                ]

            self.assertEqual(
                selected,
                [
                    ("Two", "second"),
                    ("Three", "third"),
                    ("One", "first"),
                    ("Two", "second"),
                ],
            )


if __name__ == "__main__":
    unittest.main()
