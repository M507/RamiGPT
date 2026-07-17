"""Tests for Full AI command history persistence and prompt wording."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ramigpt.domain.prompt import PrivEscPrompt
from ramigpt.utils import session_logging as sl


class PromptHistoryTests(unittest.TestCase):
    def test_prompt_states_history_did_not_get_root(self):
        priv = PrivEscPrompt("lowpriv", "secret", "Linux", "root")
        priv.add_history("id", "uid=1001(lowpriv)")
        priv.add_history(
            "sudo /usr/bin/awk 'BEGIN {system(\"id\")}'",
            "[runner] command stopped / timed out",
        )
        prompt = priv.generate_prompt()
        self.assertIn(
            "none of them got 'root' — if any had, this session would have stopped",
            prompt,
        )
        self.assertIn("Do not repeat already tried commands", prompt)
        self.assertIn("sudo /usr/bin/awk", prompt)
        # Password must never leak into the model prompt.
        self.assertNotIn("secret", prompt)

    def test_pending_then_stop_keeps_command_in_history(self):
        priv = PrivEscPrompt("lowpriv", "x", "Linux", "bench-awk")
        cmd = "sudo /usr/bin/awk 'BEGIN {system(\"id\")}'"
        priv.add_history(cmd, "")  # recorded on send
        priv.add_history(cmd, "[runner] command stopped / timed out")
        self.assertEqual(len(priv.history), 1)
        self.assertEqual(priv.history[0]["command"], cmd)
        self.assertIn("stopped", priv.history[0]["output"])
        block = priv._history_block()
        self.assertIn("none of them got 'bench-awk'", block)

    def test_empty_update_does_not_clobber_real_output(self):
        priv = PrivEscPrompt("lowpriv", "x", "Linux", "root")
        priv.add_history("id", "uid=1001(lowpriv)")
        priv.add_history("id", "")
        self.assertEqual(priv.history[0]["output"], "uid=1001(lowpriv)")

    def test_merge_history_fills_gaps_from_prior_run(self):
        priv = PrivEscPrompt("lowpriv", "x", "Linux", "root")
        priv.add_history("id", "uid=1001(lowpriv)")
        added = priv.merge_history_entries(
            [
                {"command": "id", "output": "should-not-clobber"},
                {
                    "command": "sudo /usr/bin/awk 'BEGIN {system(\"id\")}'",
                    "output": "(None — recv timed out / no prompt delimiter)",
                },
            ]
        )
        self.assertEqual(added, 1)
        cmds = [e["command"] for e in priv.history]
        self.assertEqual(cmds[0], "id")
        self.assertEqual(priv.history[0]["output"], "uid=1001(lowpriv)")
        self.assertIn("awk", cmds[1])

    def test_load_shell_command_history_from_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            sid = "test-hist-sid"
            root = Path(tmp) / sid
            run = root / "002_20260716T190200Z_connect"
            run.mkdir(parents=True)
            events = [
                {
                    "kind": "SHELL_IO",
                    "details": {
                        "command": "id",
                        "shell_output": "uid=1001(lowpriv)\n$",
                    },
                },
                {
                    "kind": "SHELL_IO",
                    "details": {
                        "command": "sudo -l",
                        "shell_output": "(ALL) NOPASSWD: /usr/bin/awk\n$",
                    },
                },
                {
                    "kind": "SHELL_IO",
                    "details": {
                        "command": "sudo /usr/bin/awk 'BEGIN {system(\"id\")}'",
                        "shell_output": None,
                        "note": "shell_recvuntil_v4 returned None",
                    },
                },
                {
                    "kind": "AI_TURN",
                    "details": {"filtered_command": "ignore-me"},
                },
            ]
            (run / "events.jsonl").write_text(
                "\n".join(json.dumps(e) for e in events) + "\n",
                encoding="utf-8",
            )

            with mock.patch.object(sl, "_session_log_root", return_value=root):
                pairs = sl.load_shell_command_history(sid)

            self.assertEqual(len(pairs), 3)
            self.assertEqual(pairs[2]["command"], "sudo /usr/bin/awk 'BEGIN {system(\"id\")}'")
            self.assertIn("None", pairs[2]["output"])

            # Simulate restart Full AI: memory has only manual cmds; logs restore awk.
            priv = PrivEscPrompt("lowpriv", "x", "Linux", "root")
            priv.add_history("id", "uid=1001(lowpriv)\n$")
            priv.add_history("sudo -l", "(ALL) NOPASSWD: /usr/bin/awk\n$")
            added = priv.merge_history_entries(pairs)
            self.assertEqual(added, 1)
            prompt = priv.generate_prompt()
            self.assertIn("sudo /usr/bin/awk", prompt)
            self.assertIn("none of them got 'root'", prompt)
            self.assertIn("Do not repeat already tried commands", prompt)


if __name__ == "__main__":
    unittest.main()
