"""Policy-violation detection for empty AI commands."""

from __future__ import annotations

import unittest

from ramigpt.ai.refusal import POLICY_BLOCK_REASON, detect_policy_violation


class DetectPolicyViolationTests(unittest.TestCase):
    def test_anthropic_usage_policy_block(self):
        raw = (
            "This request triggered restrictions on violative cyber content and was "
            "blocked under Anthropic's Usage Policy. To learn more, see "
            "https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback."
        )
        self.assertEqual(detect_policy_violation(raw), POLICY_BLOCK_REASON)

    def test_normal_command_is_not_a_block(self):
        self.assertIsNone(detect_policy_violation("sudo -l"))
        self.assertIsNone(detect_policy_violation("sudo /usr/bin/vim -es -c ':!id'"))
        self.assertIsNone(detect_policy_violation(""))
        self.assertIsNone(detect_policy_violation(None))  # type: ignore[arg-type]

    def test_generic_cannot_assist(self):
        self.assertEqual(
            detect_policy_violation("I can't assist with that request."),
            POLICY_BLOCK_REASON,
        )


if __name__ == "__main__":
    unittest.main()
