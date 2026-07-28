"""Tests for explicit collab result saving."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ramigpt.benchmark.orchestrator as orchestrator
from ramigpt.benchmark.orchestrator import (
    BenchmarkRun,
    _stage_collab_result,
    clear_pending_collab,
    save_collab_results,
)


class BenchmarkCollabSaveTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_pending_collab()

    def tearDown(self) -> None:
        clear_pending_collab()

    def test_stage_does_not_write_result_json(self) -> None:
        run = BenchmarkRun(
            id="test-run-001",
            mode="remote",
            timeout_seconds=60,
            phase="done",
            provider="openai",
            model="gpt-test",
            model_key_name="gpt-test-key",
        )
        with tempfile.TemporaryDirectory() as tmp:
            results_root = Path(tmp) / "results"
            with patch("ramigpt.benchmark.orchestrator.write_benchmark_result") as mock_write:
                _stage_collab_result(run)
                mock_write.assert_not_called()
            self.assertIn(run.id, orchestrator._pending_collab["runs"])

    def test_save_writes_staged_results(self) -> None:
        run = BenchmarkRun(
            id="test-run-002",
            mode="remote",
            timeout_seconds=60,
            phase="done",
            provider="openai",
            model="gpt-test",
            model_key_name="gpt-test-key",
        )
        _stage_collab_result(run)
        with tempfile.TemporaryDirectory() as tmp:
            results_root = Path(tmp) / "results"
            results_root.mkdir(parents=True)
            fake_path = results_root / "20260721T000000Z_test-run" / "result.json"
            fake_path.parent.mkdir(parents=True)
            fake_path.write_text(json.dumps({"id": run.id}), encoding="utf-8")
            with patch(
                "ramigpt.benchmark.orchestrator.write_benchmark_result",
                return_value=fake_path,
            ) as mock_write:
                out = save_collab_results()
            self.assertTrue(out["ok"])
            mock_write.assert_called_once()
            self.assertEqual(orchestrator._pending_collab["runs"], {})

    def test_save_without_pending_returns_error(self) -> None:
        clear_pending_collab()
        out = save_collab_results()
        self.assertFalse(out["ok"])
        self.assertIn("No unsaved", out["error"])


if __name__ == "__main__":
    unittest.main()
