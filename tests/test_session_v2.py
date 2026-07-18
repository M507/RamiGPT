"""Tests for Upgraded Session v2 command extraction and normalization."""

from __future__ import annotations

import unittest
from unittest import mock

from ramigpt.config.settings import Settings
from ramigpt.session_v2.extraction import extract_command_from_response
from ramigpt.session_v2.interactive import InteractiveSessionDriver
from ramigpt.session_v2.normalize import prepare_command
from ramigpt.session_v2.resolve import resolve_ai_command
from ramigpt.session_v2.runner import is_enabled
from ramigpt.session_v2.types import ShellBridge


class SessionV2ExtractionTests(unittest.TestCase):
    def test_prefers_fenced_command_over_prose(self):
        raw = (
            "The next command should target sudo.\n\n"
            "**Command:**\n"
            "```bash\nsudo -i\n```\n"
        )
        self.assertEqual(extract_command_from_response(raw), "sudo -i")

    def test_prefers_backtick_command_over_prose(self):
        raw = (
            "To escalate privileges using vim:\n\n"
            "**Command:**\n"
            "`sudo visudo`\n"
        )
        self.assertEqual(extract_command_from_response(raw), "sudo visudo")

    def test_ignores_prose_only_response(self):
        raw = "The next command should target the identified vulnerability with sudo."
        self.assertIsNone(extract_command_from_response(raw))

    def test_extracts_inline_shell_command(self):
        self.assertEqual(
            extract_command_from_response("sudo awk 'BEGIN {system(\"id\")}'"),
            "sudo awk 'BEGIN {system(\"id\")}'",
        )


class SessionV2NormalizeTests(unittest.TestCase):
    def test_rewrites_interactive_sudo_shells(self):
        self.assertEqual(prepare_command("sudo -i"), "sudo -n id")
        self.assertEqual(prepare_command("sudo su -"), "sudo -n id")
        self.assertEqual(prepare_command("sudo bash"), 'sudo -n bash -c "id; cat /root/flag.txt 2>/dev/null"')

    def test_rewrites_malformed_awk_shell_drop(self):
        raw = (
            "sudo awk -f /dev/null '/./{print(\"UID=\",$1); "
            'system(sprintf("/bin/sh",))};'
            "'"
        )
        self.assertEqual(
            prepare_command(raw),
            """sudo /usr/bin/awk 'BEGIN {system("id")}'""",
        )

    def test_rewrites_visudo(self):
        prepared = prepare_command("sudo visudo")
        self.assertIn("/usr/bin/vim", prepared)
        self.assertIn("-es", prepared)
        self.assertIn(":!id", prepared)

    def test_adds_ex_mode_to_vim_command(self):
        prepared = prepare_command(
            "sudo /usr/bin/vim -c ':!id' -c ':q!' /dev/null"
        )
        self.assertIn("-es", prepared)

    def test_rewrites_bare_sudo_vim(self):
        prepared = prepare_command("sudo vim /etc/passwd")
        self.assertIn("-c ':!id'", prepared)
        self.assertIn(":q!", prepared)


class SessionV2ResolveTests(unittest.TestCase):
    def test_resolve_uses_v2_when_enabled(self):
        priv = mock.Mock()
        raw = "```bash\nsudo id\n```"
        with mock.patch("ramigpt.session_v2.resolve.is_enabled", return_value=True):
            self.assertEqual(resolve_ai_command(raw, priv), "sudo id")
        priv.filter_output.assert_not_called()

    def test_resolve_uses_legacy_when_disabled(self):
        priv = mock.Mock()
        priv.filter_output.return_value = "id"
        with mock.patch("ramigpt.session_v2.resolve.is_enabled", return_value=False):
            self.assertEqual(resolve_ai_command("id", priv), "id")
        priv.filter_output.assert_called_once()


class SessionV2SettingsTests(unittest.TestCase):
    def test_enabled_by_default(self):
        with mock.patch("ramigpt.session_v2.runner.get_settings") as get_settings:
            get_settings.return_value = Settings(upgraded_session_v2=1)
            self.assertTrue(is_enabled())

    def test_disabled_when_setting_off(self):
        with mock.patch("ramigpt.session_v2.runner.get_settings") as get_settings:
            get_settings.return_value = Settings(upgraded_session_v2=0)
            self.assertFalse(is_enabled())


class SessionV2InteractiveDriverTests(unittest.TestCase):
    def test_detects_root_during_drive(self):
        shell = mock.Mock()
        bridge = ShellBridge(
            recv_until_v4=mock.Mock(),
            interrupt_shell=mock.Mock(),
            is_prompt_line=lambda line: line.endswith("$"),
            looks_like_editor_stuck=lambda text: False,
            try_quit_editor=lambda shell: "",
            looks_like_password_prompt=lambda text: False,
            still_waiting_on_password=lambda text: False,
            answer_password_prompt=lambda *args, **kwargs: "",
            recv_for_duration=lambda shell, duration: b"uid=0(root) gid=0(root) groups=0(root)\n$ ",
            safe_decode=lambda data: str(data),
            sleep=lambda seconds: None,
        )
        driver = InteractiveSessionDriver(
            bridge=bridge,
            hostname="bench-vim",
            password="password",
            timeout=1.0,
        )
        result = driver.execute(shell, "sudo -n id")
        self.assertTrue(result.got_root)
        shell.sendline.assert_any_call("sudo -n id")


if __name__ == "__main__":
    unittest.main()
