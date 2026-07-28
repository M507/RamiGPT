"""Tests for benchmark root / flag detection."""

from __future__ import annotations

import unittest

from ramigpt.benchmark.targets import BENCH_FLAG
from ramigpt.domain.root_detection import diagnose_root, got_root


class RootDetectionFlagTests(unittest.TestCase):
    def test_flag_in_cat_output_counts_as_root(self):
        output = f"$ cat /root/flag.txt\n{BENCH_FLAG}\n$ "
        diag = diagnose_root("bench-detect", output)
        self.assertTrue(diag["got_root"])
        self.assertIn("flag", diag["reason"].lower())
        self.assertTrue(got_root("bench-detect", output))

    def test_flag_without_uid_or_prompt_still_wins(self):
        output = f"some tool output\n{BENCH_FLAG}\n"
        self.assertTrue(got_root("x", output))

    def test_no_false_positive_without_flag(self):
        output = "uid=1000(lowpriv) gid=1000(lowpriv)\n$ "
        self.assertFalse(got_root("bench-vim", output))


if __name__ == "__main__":
    unittest.main()
