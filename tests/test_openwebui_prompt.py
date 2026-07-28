"""Tests for Open WebUI prompt sanitization."""

from __future__ import annotations

import unittest

from ramigpt.ai.openwebui_prompt import (
    OPENWEBUI_SAFE_SYSTEM,
    PENTESTER_SYSTEM,
    prepare_openwebui_messages,
    sanitize_for_openwebui,
)


SAMPLE_BEROOT = """
################ Suid Binaries  ################
/usr/bin/su
[+] gtfobins found:
/usr/bin/passwd
[+] gtfobins found:
\t- echo "/bin/sh <$(tty) >$(tty) 2>$(tty)" | sudo at now; tail -f /dev/null
/usr/bin/at
################ Exploits ################
Possible Exploits:
[+] [CVE-2021-3156] sudo Baron Samedit
################ sudo -l (runner capture) ################
User lowpriv may run the following commands on ubuntu:
    (ALL) NOPASSWD: /usr/bin/vim
""".strip()


class OpenWebUIPromptSanitizeTests(unittest.TestCase):
    def test_strips_gtfo_payloads_and_exploit_section(self):
        cleaned = sanitize_for_openwebui(SAMPLE_BEROOT)
        self.assertIn("/usr/bin/vim", cleaned)
        self.assertIn("NOPASSWD", cleaned)
        self.assertIn("/usr/bin/passwd", cleaned)
        self.assertNotIn("gtfobins", cleaned.lower())
        self.assertNotIn("/bin/sh", cleaned)
        self.assertNotIn("CVE-2021-3156", cleaned)

    def test_preserves_suid_paths(self):
        cleaned = sanitize_for_openwebui(SAMPLE_BEROOT)
        self.assertIn("/usr/bin/su", cleaned)
        self.assertIn("/usr/bin/at", cleaned)

    def test_strips_password_runner_instruction(self):
        text = (
            "Commands must be non-interactive and safe to run in /bin/sh. "
            "If a tool prompts for this account's password, the runner supplies it "
            "automatically — never print or echo the password."
        )
        cleaned = sanitize_for_openwebui(text)
        self.assertIn("non-interactive", cleaned)
        self.assertNotIn("password", cleaned.lower())

    def test_prepare_messages_replaces_pentester_system(self):
        prepared = prepare_openwebui_messages(
            [
                {"role": "system", "content": PENTESTER_SYSTEM},
                {"role": "user", "content": "State your next command only."},
            ]
        )
        self.assertEqual(prepared[0]["content"], OPENWEBUI_SAFE_SYSTEM)


if __name__ == "__main__":
    unittest.main()
