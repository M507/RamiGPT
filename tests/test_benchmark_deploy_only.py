"""Tests for deploy-only async status helpers."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from ramigpt.benchmark.deploy import (
    RemoteDeployConfig,
    get_deploy_status,
    is_deploy_only_running,
    request_stop_deploy,
    start_deploy_async,
)


class DeployOnlyAsyncTests(unittest.TestCase):
    def setUp(self):
        # Reset module state between tests.
        import ramigpt.benchmark.deploy as deploy_mod

        with deploy_mod._deploy_lock:
            deploy_mod._deploy_active = None

    def tearDown(self):
        import ramigpt.benchmark.deploy as deploy_mod

        with deploy_mod._deploy_lock:
            deploy_mod._deploy_active = None

    def test_idle_status(self):
        status = get_deploy_status()
        self.assertFalse(status["running"])
        self.assertEqual(status["phase"], "idle")
        self.assertIsNone(status["run"])
        self.assertFalse(is_deploy_only_running())

    def test_stop_when_idle(self):
        result = request_stop_deploy()
        self.assertFalse(result["ok"])

    @patch("ramigpt.benchmark.deploy.ensure_remote_benchmark")
    @patch("ramigpt.benchmark.orchestrator.get_status", return_value={"running": False})
    def test_start_rejects_empty_targets(self, _bench_status, _ensure):
        cfg = RemoteDeployConfig(host="10.0.0.1", username="root", password="x")
        with self.assertRaises(ValueError):
            start_deploy_async(cfg, target_ids=[])

    @patch("ramigpt.benchmark.deploy.ensure_remote_benchmark")
    @patch("ramigpt.benchmark.orchestrator.get_status", return_value={"running": True})
    def test_start_rejects_when_benchmark_running(self, _bench_status, _ensure):
        cfg = RemoteDeployConfig(host="10.0.0.1", username="root", password="x")
        with self.assertRaises(RuntimeError):
            start_deploy_async(cfg, target_ids=["sudo-vim"])

    @patch("ramigpt.benchmark.deploy.ensure_remote_benchmark")
    @patch("ramigpt.benchmark.orchestrator.get_status", return_value={"running": False})
    def test_start_runs_ensure_and_completes(self, _bench_status, ensure_mock):
        cfg = RemoteDeployConfig(host="10.0.0.1", username="root", password="x")
        ensure_mock.return_value = "10.0.0.1"
        run = start_deploy_async(cfg, target_ids=["sudo-vim"], force_redeploy=True)
        self.assertTrue(run["running"] or run["phase"] in {"starting", "deploying", "done"})
        self.assertIn("sudo-vim", run["target_ids"])

        # Wait briefly for the daemon thread.
        import time

        for _ in range(50):
            status = get_deploy_status()
            if not status["running"]:
                break
            time.sleep(0.05)

        status = get_deploy_status()
        self.assertFalse(status["running"])
        self.assertIsNotNone(status["run"])
        self.assertEqual(status["run"]["phase"], "done")
        self.assertTrue(status["run"]["ok"])
        ensure_mock.assert_called_once()
        kwargs = ensure_mock.call_args.kwargs
        self.assertTrue(kwargs.get("force_deploy"))


if __name__ == "__main__":
    unittest.main()
