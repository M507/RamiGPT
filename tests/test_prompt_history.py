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
    def test_custom_role_objective_renders_session_placeholders(self):
        priv = PrivEscPrompt("lowpriv", "secret", "Linux", "root")

        prompt = priv.generate_prompt(
            role_objective=(
                "Operate as {username} on {system}; become {target_user}."
            )
        )

        self.assertTrue(
            prompt.startswith("Operate as lowpriv on Linux; become root.")
        )
        self.assertNotIn("You are a low-privilege user", prompt)

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
        block = priv._history_block(include_outputs=True)
        self.assertIn("none of them got 'bench-awk'", block)

    def test_history_defaults_to_commands_without_outputs(self):
        priv = PrivEscPrompt("lowpriv", "x", "Linux", "root")
        priv.add_history("command-one", "output-one")
        priv.add_history("command-two", "output-two")

        prompt = priv.generate_prompt()

        self.assertIn("command-one", prompt)
        self.assertIn("command-two", prompt)
        self.assertNotIn("output-one", prompt)
        self.assertNotIn("output-two", prompt)

    def test_history_outputs_include_first_and_last_n(self):
        priv = PrivEscPrompt("lowpriv", "x", "Linux", "root")
        for index in range(1, 7):
            priv.add_history(f"command-{index}", f"output-{index}")

        prompt = priv.generate_prompt(
            include_history_outputs=True,
            history_output_edge_count=2,
        )

        for index in range(1, 7):
            self.assertIn(f"command-{index}", prompt)
        for index in (1, 2, 5, 6):
            self.assertIn(f"output-{index}", prompt)
        for index in (3, 4):
            self.assertNotIn(f"output-{index}", prompt)

    def test_zero_history_output_count_includes_all_outputs(self):
        priv = PrivEscPrompt("lowpriv", "x", "Linux", "root")
        for index in range(1, 5):
            priv.add_history(f"command-{index}", f"output-{index}")

        prompt = priv.generate_prompt(
            include_history_outputs=True,
            history_output_edge_count=0,
        )

        for index in range(1, 5):
            self.assertIn(f"output-{index}", prompt)

    def test_beroot_comes_before_command_history(self):
        priv = PrivEscPrompt("lowpriv", "x", "Linux", "root")
        priv.set_BeRoot("SUID: /usr/bin/vim", persist=True)
        priv.add_history("id", "uid=1001(lowpriv)")

        prompt = priv.generate_prompt()
        beroot_at = prompt.index("The following output is from BeRoot scanner:")
        history_at = prompt.index("You already tried the following commands")
        self.assertLess(beroot_at, history_at)
        self.assertLess(prompt.index("SUID: /usr/bin/vim"), history_at)

    def test_beroot_persists_across_full_ai_turns_by_default(self):
        priv = PrivEscPrompt("lowpriv", "x", "Linux", "root")
        priv.set_BeRoot("rule: /usr/bin/awk")
        priv.add_history("id", "uid=1001(lowpriv)")

        first = priv.generate_prompt()
        second = priv.generate_prompt()

        self.assertIn("The following output is from BeRoot scanner:", first)
        self.assertIn("rule: /usr/bin/awk", first)
        self.assertIn("The following output is from BeRoot scanner:", second)
        self.assertIn("rule: /usr/bin/awk", second)
        self.assertIn("id", second)

    def test_beroot_one_shot_only_when_persist_false(self):
        priv = PrivEscPrompt("lowpriv", "x", "Linux", "root")
        priv.set_BeRoot("SUID: /usr/bin/vim", persist=False)

        first = priv.generate_prompt()
        second = priv.generate_prompt()

        self.assertIn("SUID: /usr/bin/vim", first)
        self.assertNotIn("The following output is from BeRoot scanner:", second)

    def test_copy_scanner_findings_from_restores_context(self):
        source = PrivEscPrompt("lowpriv", "x", "Linux", "root")
        source.set_BeRoot("NOPASSWD: /usr/bin/awk")
        source.set_LinPEAS("peas output")

        dest = PrivEscPrompt("lowpriv", "x", "Linux", "root")
        dest.copy_scanner_findings_from(source)
        prompt = dest.generate_prompt()

        self.assertIn("BeRoot scanner", prompt)
        self.assertIn("NOPASSWD: /usr/bin/awk", prompt)
        self.assertIn("LinPEAS scanner", prompt)
        self.assertIn("peas output", prompt)

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
