"""Tests for benchmark misconfig verification."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ramigpt.benchmark.targets import BENCH_FLAG, TARGETS
from ramigpt.benchmark.verify import (
    _output_contains_flag,
    _run_one_check,
    write_catalog,
)


class BenchmarkVerifyCatalogTests(unittest.TestCase):
    def test_write_catalog_includes_every_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "catalog.tsv"
            write_catalog(path)
            lines = [
                line
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")
            ]
        self.assertEqual(len(lines), len(TARGETS))
        first = lines[0].split("\t")
        self.assertEqual(first[0], TARGETS[0].id)


class BenchmarkVerifyRunOneCheckTests(unittest.TestCase):
    def test_missing_script_fails(self):
        result = _run_one_check(
            host="127.0.0.1",
            target_id="definitely-not-a-target",
            port=9999,
            expects_root=True,
            user="lowpriv",
            password="password",
        )
        self.assertEqual(result.status, "fail")
        self.assertIn("missing check script", result.detail)

    @patch("ramigpt.benchmark.verify.subprocess.run")
    def test_expects_root_passes_when_script_prints_flag(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = f"OK: flag found\n{BENCH_FLAG}\n"
        mock_run.return_value.stderr = ""

        result = _run_one_check(
            host="127.0.0.1",
            target_id="sudo-vim",
            port=2211,
            expects_root=True,
            user="lowpriv",
            password="password",
        )
        self.assertEqual(result.status, "pass")

    @patch("ramigpt.benchmark.verify.subprocess.run")
    def test_expects_root_fails_on_nonzero_exit(self, mock_run):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = "permission denied"
        mock_run.return_value.stderr = ""

        result = _run_one_check(
            host="127.0.0.1",
            target_id="sudo-vim",
            port=2211,
            expects_root=True,
            user="lowpriv",
            password="password",
        )
        self.assertEqual(result.status, "fail")

    @patch("ramigpt.benchmark.verify.subprocess.run")
    def test_detect_only_flags_when_signal_ok_but_no_flag(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "nfs export detected"
        mock_run.return_value.stderr = ""

        with patch("ramigpt.benchmark.verify._probe_flag_via_ssh", return_value=False):
            result = _run_one_check(
                host="127.0.0.1",
                target_id="nfs-exports",
                port=2220,
                expects_root=False,
                user="lowpriv",
                password="password",
            )
        self.assertEqual(result.status, "flagged")

    @patch("ramigpt.benchmark.verify.subprocess.run")
    def test_detect_only_passes_when_flag_visible(self, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = f"detect ok\n{BENCH_FLAG}\n"
        mock_run.return_value.stderr = ""

        result = _run_one_check(
            host="127.0.0.1",
            target_id="nfs-exports",
            port=2220,
            expects_root=False,
            user="lowpriv",
            password="password",
        )
        self.assertEqual(result.status, "pass")


class BenchmarkVerifyFlagTests(unittest.TestCase):
    def test_output_contains_flag(self):
        self.assertTrue(_output_contains_flag(f"output\n{BENCH_FLAG}\n"))
        self.assertFalse(_output_contains_flag("uid=1000(lowpriv)"))


if __name__ == "__main__":
    unittest.main()
