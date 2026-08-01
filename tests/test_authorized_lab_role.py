"""Authorized Lab Validator role — framing for safety-aligned models."""

from __future__ import annotations

import unittest

from ramigpt.config.settings import get_role_objective, load_role_objectives
from ramigpt.domain.prompt import PrivEscPrompt


class AuthorizedLabRoleTests(unittest.TestCase):
    def test_catalog_includes_authorized_lab_validator(self):
        roles = load_role_objectives()
        self.assertIn("Authorized Lab Validator", roles)
        text = roles["Authorized Lab Validator"]
        self.assertIn("{username}", text)
        self.assertIn("{system}", text)
        self.assertIn("{target_user}", text)
        self.assertIn("Reasoning for this role:", text)
        self.assertIn("authorized", text.lower())

    def test_prompt_uses_lab_framing_not_abuse_trailer(self):
        objective = get_role_objective("Authorized Lab Validator")
        prompt = PrivEscPrompt(
            "lowpriv", "x", "lab-host", "root"
        ).generate_prompt(role_objective=objective)
        self.assertIn("authorized, owner-operated Linux lab", prompt)
        self.assertIn("lowpriv", prompt)
        self.assertIn("root", prompt)
        self.assertIn("stated lab objective", prompt)
        self.assertNotIn("privilege escalation", prompt.lower())
        self.assertNotIn("by abusing commands", prompt)


if __name__ == "__main__":
    unittest.main()
