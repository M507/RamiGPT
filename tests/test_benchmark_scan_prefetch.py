"""Integration tests for benchmark scan prefetch and LinPEAS wiring."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import ramigpt.benchmark.orchestrator as orchestrator
from ramigpt.benchmark.orchestrator import (
    BenchmarkRun,
    TargetRunResult,
    _run_targets_for_run,
)
from ramigpt.benchmark.targets import TARGETS


def _linpeas_targets() -> list:
    wanted = {"sudo-vim", "sudo-awk", "sudo-all"}
    return [t for t in TARGETS if t.id in wanted]


class BenchmarkScanPrefetchTests(unittest.TestCase):
    def tearDown(self) -> None:
        orchestrator._scan_prefetch_by_run.clear()

    def test_run_targets_prefetches_linpeas_for_serial_multi_target(self) -> None:
        run = BenchmarkRun(
            id="prefetch-run",
            mode="remote",
            timeout_seconds=180,
            host="10.10.1.109",
            tools={"beroot": False, "linenum": False, "linpeas": True},
            targets=[
                TargetRunResult(target_id="sudo-vim", name="sudo vim", port=2211),
                TargetRunResult(target_id="sudo-awk", name="sudo awk", port=2212),
                TargetRunResult(target_id="sudo-all", name="sudo ALL", port=2170),
            ],
        )
        selected = _linpeas_targets()
        prefetch_calls: list[str] = []
        run_target_calls: list[str] = []

        def fake_prefetch(current_run, pending, tool_id) -> None:
            self.assertEqual(tool_id, "linpeas")
            self.assertEqual(len(pending), 3)
            for item, _target in pending:
                prefetch_calls.append(item.target_id)
                orchestrator._scan_prefetch_by_run[current_run.id] = {
                    item.session_id or f"sess-{item.target_id}": orchestrator._ScanPrefetch(
                        tool_id=tool_id
                    )
                }
                item.session_id = item.session_id or f"sess-{item.target_id}"

        def fake_run_target(current_run, item, target) -> None:
            run_target_calls.append(item.target_id)
            item.status = "passed"
            item.message = "ok"

        with patch.object(orchestrator, "_benchmark_parallel_workers", return_value=1), patch.object(
            orchestrator, "_prefetch_benchmark_scans", side_effect=fake_prefetch
        ) as prefetch_mock, patch.object(
            orchestrator, "_run_target", side_effect=fake_run_target
        ) as run_target_mock:
            _run_targets_for_run(run, selected)

        prefetch_mock.assert_called_once()
        self.assertEqual(
            prefetch_calls,
            ["sudo-vim", "sudo-awk", "sudo-all"],
        )
        self.assertEqual(
            run_target_calls,
            ["sudo-vim", "sudo-awk", "sudo-all"],
        )
        run_target_mock.assert_called()
        self.assertEqual(run_target_mock.call_count, 3)
        self.assertNotIn("prefetch-run", orchestrator._scan_prefetch_by_run)

    def test_tool_scan_uses_registered_execute_hook_with_ai_off(self) -> None:
        run = BenchmarkRun(
            id="scan-only",
            mode="remote",
            timeout_seconds=180,
            tools={"linpeas": True},
            targets=[TargetRunResult(target_id="sudo-vim", name="sudo vim", port=2211)],
        )
        captured: dict[str, object] = {}

        def fake_execute(session_data) -> None:
            captured.update(session_data)
            result = session_data.get("scan_result")
            if isinstance(result, dict):
                result["ok"] = True

        orchestrator._hooks["execute_linpeas"] = fake_execute
        with patch.object(orchestrator, "_session_data", return_value={"sid": "sess-1"}):
            orchestrator._run_tool_scan(run, "sess-1", "linpeas")

        self.assertFalse(captured.get("with_ai"))
        self.assertTrue(captured.get("from_benchmark"))
        self.assertTrue(captured.get("use_os_thread"))
        self.assertIsInstance(captured.get("scan_result"), dict)

    def test_session_is_connected_uses_registered_shell_maps(self) -> None:
        orchestrator._hooks["ssh_shells"] = {"sess-a": object()}
        orchestrator._hooks["ssh_ssh_conns"] = {}
        self.assertTrue(orchestrator._session_is_connected("sess-a"))
        self.assertFalse(orchestrator._session_is_connected("sess-b"))

    def test_session_is_connected_falls_back_to_ssh_conns(self) -> None:
        orchestrator._hooks["ssh_shells"] = {}
        orchestrator._hooks["ssh_ssh_conns"] = {"sess-b": object()}
        self.assertTrue(orchestrator._session_is_connected("sess-b"))

    def test_tool_scan_raises_when_execute_reports_failure(self) -> None:
        run = BenchmarkRun(
            id="scan-fail",
            mode="remote",
            timeout_seconds=180,
            tools={"linpeas": True},
            targets=[TargetRunResult(target_id="sudo-vim", name="sudo vim", port=2211)],
        )

        def fake_execute(session_data) -> None:
            result = session_data.get("scan_result")
            if isinstance(result, dict):
                result["ok"] = False
                result["error"] = "LinPEAS failed: Socket is closed"

        orchestrator._hooks["execute_linpeas"] = fake_execute
        with patch.object(orchestrator, "_session_data", return_value={"sid": "sess-1"}):
            with self.assertRaisesRegex(RuntimeError, "LinPEAS failed: Socket is closed"):
                orchestrator._run_tool_scan(run, "sess-1", "linpeas")


class LinpeasImportFixTests(unittest.TestCase):
    def test_scanners_execute_linpeas_uses_imported_runner(self) -> None:
        import inspect

        from ramigpt.web.tools import scanners
        from ramigpt.web.tools.beroot import _run_linpeas_on_remote

        source = inspect.getsource(scanners.execute_linpeas)
        self.assertIn("_run_linpeas_on_remote(", source)
        self.assertIs(scanners._run_linpeas_on_remote, _run_linpeas_on_remote)


if __name__ == "__main__":
    unittest.main()
