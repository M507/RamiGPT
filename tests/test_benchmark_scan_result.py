"""Tests for benchmark scan_result reporting from scanner tasks."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ramigpt.web.tools.scanners import _record_benchmark_scan_result, execute_linpeas


class BenchmarkScanResultTests(unittest.TestCase):
    def test_record_scan_result_updates_dict(self) -> None:
        session_data = {"scan_result": {"ok": False, "error": ""}}
        _record_benchmark_scan_result(
            session_data,
            ok=False,
            error="LinPEAS failed: Socket is closed",
        )
        self.assertFalse(session_data["scan_result"]["ok"])
        self.assertEqual(
            session_data["scan_result"]["error"],
            "LinPEAS failed: Socket is closed",
        )

    def test_execute_linpeas_records_failure_without_ai(self) -> None:
        session_data = {
            "sid": "sess-1",
            "with_ai": False,
            "scan_result": {"ok": False, "error": ""},
            "password": "password",
        }

        with patch("ramigpt.web.tools.scanners.app.app_context", return_value=MagicMock()), patch(
            "ramigpt.web.tools.scanners.ssh_ssh_conns", {"sess-1": object()}
        ), patch(
            "ramigpt.web.tools.scanners.get_session_logger",
            return_value=MagicMock(),
        ), patch(
            "ramigpt.web.tools.scanners._run_linpeas_on_remote",
            side_effect=RuntimeError("Socket is closed"),
        ), patch("ramigpt.web.tools.scanners.loop", {}):
            execute_linpeas(session_data)

        self.assertFalse(session_data["scan_result"]["ok"])
        self.assertIn("Socket is closed", session_data["scan_result"]["error"])


if __name__ == "__main__":
    unittest.main()
