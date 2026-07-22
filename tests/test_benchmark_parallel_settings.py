"""Tests for benchmark parallel target settings."""

from __future__ import annotations

import unittest

from ramigpt.benchmark.orchestrator import (
    BenchmarkRun,
    TargetRunResult,
    _benchmark_parallel_workers,
    _should_prefetch_scans,
)
from ramigpt.config.settings import Settings, _apply_updates


class BenchmarkParallelSettingsTests(unittest.TestCase):
    def test_validation_rejects_out_of_range(self) -> None:
        base = Settings()
        with self.assertRaises(ValueError):
            _apply_updates(base, {"benchmark_parallel_targets": 0})
        with self.assertRaises(ValueError):
            _apply_updates(base, {"benchmark_parallel_targets": 51})

    def test_validation_accepts_in_range(self) -> None:
        updated = _apply_updates(Settings(), {"benchmark_parallel_targets": 50})
        self.assertEqual(updated.benchmark_parallel_targets, 50)

    def test_workers_helper_clamps_settings(self) -> None:
        from unittest.mock import patch

        with patch("ramigpt.benchmark.orchestrator.get_settings") as mock_get:
            mock_get.return_value = Settings(benchmark_parallel_targets=50)
            self.assertEqual(_benchmark_parallel_workers(), 50)
            mock_get.return_value = Settings(benchmark_parallel_targets=999)
            self.assertEqual(_benchmark_parallel_workers(), 50)

    def test_prefetch_scans_when_serial_multi_target_with_tool(self) -> None:
        run = BenchmarkRun(
            id="test",
            mode="remote",
            timeout_seconds=180,
            tools={"beroot": False, "linenum": False, "linpeas": True},
            targets=[
                TargetRunResult(target_id="a", name="A", port=1),
                TargetRunResult(target_id="b", name="B", port=2),
            ],
        )
        self.assertTrue(_should_prefetch_scans(run, 2, 1))

    def test_prefetch_skipped_when_parallel_workers_gt_one(self) -> None:
        run = BenchmarkRun(
            id="test",
            mode="remote",
            timeout_seconds=180,
            tools={"linpeas": True},
            targets=[TargetRunResult(target_id="a", name="A", port=1)],
        )
        self.assertFalse(_should_prefetch_scans(run, 3, 2))

    def test_prefetch_skipped_without_pre_tools(self) -> None:
        run = BenchmarkRun(
            id="test",
            mode="remote",
            timeout_seconds=180,
            tools={"beroot": False, "linenum": False, "linpeas": False},
            targets=[
                TargetRunResult(target_id="a", name="A", port=1),
                TargetRunResult(target_id="b", name="B", port=2),
            ],
        )
        self.assertFalse(_should_prefetch_scans(run, 2, 1))


if __name__ == "__main__":
    unittest.main()
