"""API and page smoke tests for the benchmark leaderboard."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("PWNLIB_NOTERM", "1")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _sample_run_doc(*, run_id: str) -> dict:
    return {
        "schema_version": 2,
        "id": run_id,
        "batch_id": None,
        "repetition": 1,
        "repetitions": 1,
        "mode": "remote",
        "host": "10.0.0.1",
        "phase": "done",
        "provider": "ollama",
        "model": "qwen3:14b",
        "model_key_name": "ollama-qwen3-14b-example",
        "model_registry": {
            "key_name": "ollama-qwen3-14b-example",
            "registry_path": "data/benchmark/models/ollama-qwen3-14b-example.json",
        },
        "hardware": {
            "gpu_name": "NVIDIA GeForce RTX 4070",
            "gpu_vram": 12282,
            "cuda_version": "13.1",
        },
        "role_objective": "Privilege Escalation Pentester",
        "tools_configured": {"beroot": True},
        "tools": ["beroot"],
        "started_at": "2026-07-18T10:00:00+00:00",
        "finished_at": "2026-07-18T10:05:00+00:00",
        "targets": [
            {
                "target_id": "sudo-vim",
                "status": "passed",
                "elapsed_seconds": 60.0,
                "got_root": True,
                "provider": "ollama",
                "model": "qwen3:14b",
                "role_objective": "Privilege Escalation Pentester",
                "model_key_name": "ollama-qwen3-14b-example",
                "timing_summary": {
                    "beroot_seconds": 45.0,
                    "ai_llm_seconds": 8.0,
                    "shell_seconds": 2.0,
                    "other_seconds": 5.0,
                },
                "tokens_total": 500,
                "prompt_tokens": 450,
                "completion_tokens": 50,
                "commands_count": 2,
                "ai_requests": 2,
            }
        ],
        "summary": {
            "passed": 1,
            "failed": 0,
            "target_count": 1,
            "attempted": 1,
            "elapsed_seconds_total": 60.0,
            "tokens_total": 500,
        },
    }


class BenchmarkLeaderboardApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import ramigpt.web.app as app_module

        cls.app = app_module.app
        cls.client = cls.app.test_client()

    def test_leaderboard_page_renders(self):
        resp = self.client.get("/leaderboard")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("Model Leaderboard", html)
        self.assertIn("/static/leaderboard.js", html)
        self.assertIn("lb-chart-resolved", html)
        self.assertIn("lb-chart-radar", html)

    def test_leaderboard_api_compact_payload(self):
        from ramigpt.benchmark import master_results as master_module

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run1"
            run_dir.mkdir()
            (run_dir / "result.json").write_text(
                json.dumps(_sample_run_doc(run_id="api-1")),
                encoding="utf-8",
            )
            master = master_module.build_master_document(root)
            master_module.write_master_results(master, results_dir=root, update_readme=False)

            with patch.object(master_module, "BENCHMARK_RESULTS_DIR", root):
                resp = self.client.get("/api/benchmark/results/leaderboard?limit=6&by=got_root_count")
            self.assertEqual(resp.status_code, 200, resp.get_json())
            body = resp.get_json()
            self.assertTrue(body.get("ok"))
            self.assertEqual(body.get("limit"), 6)
            self.assertIn("top", body)
            self.assertLessEqual(len(body["top"]), 6)
            self.assertIn("charts", body)
            self.assertNotIn("aggregate", body)
            self.assertNotIn("by_scenario", body)
            # Compact: should not ship the full master document
            self.assertNotIn("master", body)
            self.assertIn("got_root_count", body["top"][0])
            self.assertIn("score_percent", body["top"][0])

    def test_leaderboard_api_no_master(self):
        from ramigpt.benchmark import master_results as master_module

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(master_module, "BENCHMARK_RESULTS_DIR", root):
                resp = self.client.get("/api/benchmark/results/leaderboard")
            self.assertEqual(resp.status_code, 404)
            body = resp.get_json()
            self.assertFalse(body.get("ok"))
            self.assertEqual(body.get("top"), [])


if __name__ == "__main__":
    unittest.main()
