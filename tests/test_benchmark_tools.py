import unittest

from ramigpt.benchmark.tools import (
    AVAILABLE_TOOLS,
    normalize_tools,
    pick_benchmark_tool,
)
from ramigpt.domain import PrivEscPrompt
from ramigpt.tools.linenum import sanitize_linenum_for_prompt
from ramigpt.tools.linpeas import sanitize_linpeas_for_prompt


class BenchmarkToolsTest(unittest.TestCase):
    def test_available_tools_includes_linenum(self):
        ids = {t["id"] for t in AVAILABLE_TOOLS}
        self.assertIn("beroot", ids)
        self.assertIn("linenum", ids)
        self.assertIn("linpeas", ids)

    def test_normalize_tools_accepts_linenum_only(self):
        out = normalize_tools({"beroot": False, "linenum": True, "linpeas": False})
        self.assertFalse(out["beroot"])
        self.assertTrue(out["linenum"])
        self.assertFalse(out["linpeas"])

    def test_normalize_tools_accepts_linpeas_only(self):
        out = normalize_tools({"beroot": False, "linenum": False, "linpeas": True})
        self.assertEqual(pick_benchmark_tool(out), "linpeas")

    def test_pick_benchmark_tool_prefers_beroot_when_both_enabled(self):
        tools = {"beroot": True, "linenum": True}
        self.assertEqual(pick_benchmark_tool(tools), "beroot")

    def test_pick_benchmark_tool_returns_linenum_when_only_linenum(self):
        tools = {"beroot": False, "linenum": True}
        self.assertEqual(pick_benchmark_tool(tools), "linenum")


class LinEnumPromptTest(unittest.TestCase):
    def test_linenum_output_in_prompt(self):
        priv = PrivEscPrompt("user", "pass", "Linux", "root")
        priv.set_LinEnum("SUID: /usr/bin/find", persist=True)
        prompt = priv.generate_prompt()
        self.assertIn("LinEnum scanner", prompt)
        self.assertIn("SUID: /usr/bin/find", prompt)

    def test_linpeas_output_in_prompt(self):
        priv = PrivEscPrompt("user", "pass", "Linux", "root")
        priv.set_LinPEAS("NOPASSWD: /usr/bin/vim", persist=True)
        prompt = priv.generate_prompt()
        self.assertIn("LinPEAS scanner", prompt)
        self.assertIn("NOPASSWD: /usr/bin/vim", prompt)

    def test_clear_scanner_findings(self):
        priv = PrivEscPrompt("user", "pass", "Linux", "root")
        priv.set_BeRoot("a", persist=True)
        priv.set_LinEnum("b", persist=True)
        priv.set_LinPEAS("c", persist=True)
        priv.clear_scanner_findings()
        self.assertIsNone(priv.BeRoot)
        self.assertIsNone(priv.LinEnum)
        self.assertIsNone(priv.LinPEAS)

    def test_sanitize_linenum_strips_ansi(self):
        raw = "\x1b[1;31m[-] test\x1b[0m\nplain line"
        cleaned = sanitize_linenum_for_prompt(raw)
        self.assertIn("plain line", cleaned)
        self.assertNotIn("\x1b", cleaned)

    def test_sanitize_linpeas_truncates_large_output(self):
        raw = "A" * 100_000
        cleaned = sanitize_linpeas_for_prompt(raw, max_chars=10_000)
        self.assertLessEqual(len(cleaned), 10_000)
        self.assertIn("truncated", cleaned)


if __name__ == "__main__":
    unittest.main()
