"""Tests for collaborative master benchmark results aggregation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ramigpt.benchmark.master_results import (
    README_BENCHMARK_END,
    README_BENCHMARK_START,
    build_master_document,
    discover_result_documents,
    format_master_markdown,
    format_master_summary,
    update_readme_benchmark_section,
    write_master_results,
)
from ramigpt.benchmark.results import write_benchmark_result


def _sample_run_doc(
    *,
    run_id: str,
    provider: str = "ollama",
    model: str = "qwen3:14b",
    model_key_name: str = "ollama-qwen3-14b-qwen3-14.8B-q4_k_m-deadbeef",
    role: str = "Enumeration-First Pentester",
    target_id: str = "sudo-vim",
    status: str = "passed",
    elapsed: float = 60.0,
    got_root: bool = True,
) -> dict:
    return {
        "schema_version": 2,
        "id": run_id,
        "batch_id": None,
        "repetition": 1,
        "repetitions": 1,
        "mode": "remote",
        "host": "10.0.0.1",
        "phase": "done",
        "provider": provider,
        "model": model,
        "model_key_name": model_key_name,
        "model_registry": {
            "key_name": model_key_name,
            "registry_path": f"data/benchmark/models/{model_key_name}.json",
        },
        "hardware": {
            "gpu_name": "NVIDIA GeForce RTX 4070",
            "gpu_vram": 12282,
            "gpu_power_limit": 200,
            "cuda_version": "13.1",
        },
        "role_objective": role,
        "tools_configured": {"beroot": True},
        "tools": ["beroot"],
        "started_at": "2026-07-18T10:00:00+00:00",
        "finished_at": "2026-07-18T10:05:00+00:00",
        "targets": [
            {
                "target_id": target_id,
                "status": status,
                "elapsed_seconds": elapsed,
                "got_root": got_root,
                "provider": provider,
                "model": model,
                "role_objective": role,
                "model_key_name": model_key_name,
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
            "passed": 1 if status == "passed" else 0,
            "failed": 1 if status == "failed" else 0,
            "target_count": 1,
            "elapsed_seconds_total": elapsed,
            "tokens_total": 500,
        },
    }


class BenchmarkMasterResultsTests(unittest.TestCase):
    def test_discover_and_aggregate_multiple_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for idx, model in enumerate(["qwen3:14b", "deepseek-r1:14b"], start=1):
                run_dir = root / f"20260718T10000{idx}Z_run{idx}"
                run_dir.mkdir(parents=True)
                doc = _sample_run_doc(
                    run_id=f"run-{idx}",
                    model=model,
                    model_key_name=f"ollama-{model.replace(':', '-')}-example",
                    elapsed=50.0 + idx,
                )
                (run_dir / "result.json").write_text(json.dumps(doc), encoding="utf-8")

            docs = discover_result_documents(root)
            self.assertEqual(len(docs), 2)

            master = build_master_document(root)
            self.assertEqual(master["source_runs_deduped"], 2)
            self.assertEqual(len(master["catalog"]["model_key_names"]), 2)
            self.assertEqual(len(master["aggregate"]["by_scenario"]), 2)

            overall = master["aggregate"]["overall"]
            self.assertEqual(overall["observations"], 2)
            self.assertEqual(overall["passed"], 2)
            self.assertEqual(overall["pass_rate"], 1.0)

            by_model = master["aggregate"]["by_model"]
            keys = list(by_model.keys())
            self.assertEqual(len(keys), 2)
            self.assertTrue(all("example" in k for k in keys))

    def test_dedupes_same_run_id_keeps_latest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            older = root / "older_run"
            newer = root / "newer_run"
            older.mkdir()
            newer.mkdir()
            old_doc = _sample_run_doc(run_id="same-id", status="failed", got_root=False)
            old_doc["finished_at"] = "2026-07-18T10:00:00+00:00"
            new_doc = _sample_run_doc(run_id="same-id", status="passed", got_root=True)
            new_doc["finished_at"] = "2026-07-18T11:00:00+00:00"
            (older / "result.json").write_text(json.dumps(old_doc), encoding="utf-8")
            (newer / "result.json").write_text(json.dumps(new_doc), encoding="utf-8")

            master = build_master_document(root)
            self.assertEqual(master["source_runs_deduped"], 1)
            self.assertEqual(master["aggregate"]["overall"]["passed"], 1)

    def test_write_master_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "20260718T100001Z_abc"
            run_dir.mkdir()
            (run_dir / "result.json").write_text(
                json.dumps(_sample_run_doc(run_id="abc")), encoding="utf-8"
            )
            master = build_master_document(root)
            path = write_master_results(master, results_dir=root)
            self.assertTrue(path.is_file())
            self.assertTrue((root / "master_summary.txt").is_file())
            summary = (root / "master_summary.txt").read_text(encoding="utf-8")
            self.assertIn("ollama/qwen3:14b", summary)
            self.assertIn("sudo-vim", summary)

    def test_update_master_after_write_benchmark_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            suite_dir = root / "suite"
            target_dir = suite_dir / "sudo-vim" / "001_run"
            target_dir.mkdir(parents=True)
            events = [
                {
                    "ts": "2026-07-18T15:00:00+00:00",
                    "kind": "FULL_AI_START",
                    "details": {"provider": "ollama", "model": "qwen3:14b"},
                },
                {
                    "ts": "2026-07-18T15:00:10+00:00",
                    "kind": "AI_TURN",
                    "details": {
                        "filtered_command": "sudo vim",
                        "duration_seconds": 5.0,
                        "prompt_tokens": 100,
                        "completion_tokens": 10,
                        "total_tokens": 110,
                    },
                },
                {
                    "ts": "2026-07-18T15:00:15+00:00",
                    "kind": "FULL_AI_END",
                    "details": {"requests_run": 1, "got_root": True},
                },
            ]
            (target_dir / "events.jsonl").write_text(
                "\n".join(json.dumps(e) for e in events) + "\n",
                encoding="utf-8",
            )

            import ramigpt.benchmark.results as results_module
            import ramigpt.benchmark.master_results as master_module

            original_results_dir = results_module.BENCHMARK_RESULTS_DIR
            original_master_dir = master_module.BENCHMARK_RESULTS_DIR
            try:
                results_module.BENCHMARK_RESULTS_DIR = root
                master_module.BENCHMARK_RESULTS_DIR = root
                run_public = {
                    "id": "integration-run",
                    "targets": [{"target_id": "sudo-vim", "status": "passed", "elapsed_seconds": 15.0}],
                    "log_dir": str(suite_dir),
                    "phase": "done",
                    "mode": "remote",
                    "host": "10.0.0.2",
                    "role_objective": "Direct Privilege Escalation Operator",
                    "finished_at": "2026-07-18T15:00:20+00:00",
                }
                write_benchmark_result(
                    run_public,
                    settings={"provider": "ollama", "model": "qwen3:14b"},
                )
                master_path = root / "master.json"
                self.assertTrue(master_path.is_file())
                master = json.loads(master_path.read_text(encoding="utf-8"))
                self.assertEqual(master["source_runs_deduped"], 1)
                self.assertIn(
                    "Direct Privilege Escalation Operator",
                    master["catalog"]["roles"],
                )
            finally:
                results_module.BENCHMARK_RESULTS_DIR = original_results_dir
                master_module.BENCHMARK_RESULTS_DIR = original_master_dir

    def test_rankings_include_scenario_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run1"
            run_dir.mkdir()
            (run_dir / "result.json").write_text(
                json.dumps(_sample_run_doc(run_id="r1")), encoding="utf-8"
            )
            master = build_master_document(root)
            scenarios = master["rankings"]["scenarios"]
            self.assertEqual(len(scenarios), 1)
            row = scenarios[0]
            self.assertEqual(row["target_id"], "sudo-vim")
            self.assertEqual(row["pass_rate"], 1.0)
            self.assertEqual(row["tools"], ["beroot"])
            self.assertIn("hardware_key", row)
            text = format_master_summary(master)
            self.assertIn("Scenarios (model · hardware · role · target · tools)", text)

    def test_format_master_markdown_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run1"
            run_dir.mkdir()
            (run_dir / "result.json").write_text(
                json.dumps(_sample_run_doc(run_id="r1")), encoding="utf-8"
            )
            master = build_master_document(root)
            md = format_master_markdown(master)
            self.assertIn("| Profile |", md)
            self.assertIn("12282 MiB", md)
            self.assertIn("| Tools |", md)
            self.assertIn("`beroot`", md)
            self.assertIn("#### Overall — ollama-qwen3-14b", md)
            self.assertIn("| Mean tokens to root |", md)
            self.assertNotIn("**Mean tokens to root**", md)
            self.assertNotIn("#### Recent runs", md)
            self.assertIn("Runs merge when profile", md)
            self.assertIn("ollama-qwen3-14b", md)
            self.assertIn("master.json", md)

    def test_update_readme_benchmark_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            readme = root / "README.md"
            readme.write_text(
                "# Demo\n\n"
                f"{README_BENCHMARK_START}\nold\n{README_BENCHMARK_END}\n",
                encoding="utf-8",
            )
            run_dir = root / "run1"
            run_dir.mkdir()
            (run_dir / "result.json").write_text(
                json.dumps(_sample_run_doc(run_id="r1")), encoding="utf-8"
            )
            master = build_master_document(root)
            ok = update_readme_benchmark_section(master, readme_path=readme)
            self.assertTrue(ok)
            text = readme.read_text(encoding="utf-8")
            self.assertIn("ollama-qwen3-14b", text)
            self.assertNotIn("old", text)
            self.assertIn(README_BENCHMARK_START, text)
            self.assertIn(README_BENCHMARK_END, text)

    def test_reset_benchmark_results_clears_and_rebuilds_empty_master(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run1"
            run_dir.mkdir()
            (run_dir / "result.json").write_text(
                json.dumps(_sample_run_doc(run_id="r1")), encoding="utf-8"
            )
            import ramigpt.benchmark.master_results as master_module

            original_dir = master_module.BENCHMARK_RESULTS_DIR
            try:
                master_module.BENCHMARK_RESULTS_DIR = root
                from ramigpt.benchmark.master_results import reset_benchmark_results

                out = reset_benchmark_results(results_dir=root)
                self.assertGreaterEqual(out["removed"], 1)
                self.assertEqual(out["runs"], 0)
                self.assertFalse(list(root.rglob("result.json")))
                self.assertTrue((root / "master.json").is_file())
                master = json.loads((root / "master.json").read_text(encoding="utf-8"))
                self.assertEqual(master["source_runs_deduped"], 0)
            finally:
                master_module.BENCHMARK_RESULTS_DIR = original_dir


    def test_got_root_token_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            success = root / "ok"
            fail = root / "bad"
            success.mkdir()
            fail.mkdir()
            (success / "result.json").write_text(
                json.dumps(_sample_run_doc(run_id="ok", status="passed", elapsed=40.0)),
                encoding="utf-8",
            )
            fail_doc = _sample_run_doc(run_id="bad", status="failed", elapsed=90.0)
            fail_doc["targets"][0]["tokens_total"] = 900
            fail_doc["targets"][0]["got_root"] = False
            (fail / "result.json").write_text(json.dumps(fail_doc), encoding="utf-8")

            master = build_master_document(root)
            overall = master["aggregate"]["overall"]
            self.assertEqual(overall["got_root_count"], 1)
            self.assertEqual(overall["mean_tokens_to_root"], 500.0)
            self.assertEqual(overall["mean_elapsed_to_root"], 40.0)
            self.assertEqual((overall["tokens_total"] or {}).get("mean"), 700.0)

            model_stats = next(iter(master["aggregate"]["by_model"].values()))
            self.assertEqual(model_stats["mean_tokens_to_root"], 500.0)

            ranking = master["rankings"]["models"]["by_tokens_to_root"][0]
            self.assertEqual(ranking["mean_tokens_to_root"], 500.0)

    def test_overall_failed_count_not_overwritten_by_outcome_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run1"
            run_dir.mkdir()
            (run_dir / "result.json").write_text(
                json.dumps(_sample_run_doc(run_id="r1", status="failed", got_root=False)),
                encoding="utf-8",
            )
            overall = build_master_document(root)["aggregate"]["overall"]
            self.assertEqual(overall["failed"], 1)
            self.assertIsInstance(overall["failed"], int)
            self.assertIn("failed_outcomes", overall)
            self.assertIsInstance(overall["failed_outcomes"], dict)

    def test_write_master_skips_project_readme_for_temp_results_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            readme = root / "README.md"
            readme.write_text(
                f"# Demo\n\n{README_BENCHMARK_START}\nkeep\n{README_BENCHMARK_END}\n",
                encoding="utf-8",
            )
            run_dir = root / "results" / "run1"
            run_dir.mkdir(parents=True)
            (run_dir / "result.json").write_text(
                json.dumps(_sample_run_doc(run_id="r1")), encoding="utf-8"
            )
            master = build_master_document(root / "results")
            before = readme.read_text(encoding="utf-8")
            write_master_results(master, results_dir=root / "results")
            after = readme.read_text(encoding="utf-8")
            self.assertEqual(before, after)
            self.assertIn("keep", after)
            ok = update_readme_benchmark_section(master, readme_path=readme)
            self.assertTrue(ok)
            self.assertIn("ollama-qwen3-14b", readme.read_text(encoding="utf-8"))

    def test_tools_from_configured_and_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            configured = root / "configured"
            configured.mkdir()
            cfg_doc = _sample_run_doc(run_id="cfg")
            (configured / "result.json").write_text(
                json.dumps(cfg_doc),
                encoding="utf-8",
            )

            fallback = root / "fallback"
            fallback.mkdir()
            fb_doc = _sample_run_doc(run_id="fb")
            fb_doc.pop("tools", None)
            fb_doc.pop("tools_configured", None)
            fb_doc["summary"] = {"passed": 1, "target_count": 1, "tools_used_any": ["beroot"]}
            (fallback / "result.json").write_text(json.dumps(fb_doc), encoding="utf-8")

            none_tools = root / "none"
            none_tools.mkdir()
            none_doc = _sample_run_doc(run_id="none")
            none_doc["tools_configured"] = {"beroot": False}
            none_doc["tools"] = []
            (none_tools / "result.json").write_text(json.dumps(none_doc), encoding="utf-8")

            master = build_master_document(root)
            by_id = {row["id"]: row for row in master["runs_index"]}
            self.assertEqual(by_id["cfg"]["tools"], ["beroot"])
            self.assertEqual(by_id["fb"]["tools"], ["beroot"])
            self.assertEqual(by_id["none"]["tools"], [])

            scenario_keys = list(master["aggregate"]["by_scenario"].keys())
            self.assertEqual(len(scenario_keys), 2)
            self.assertTrue(any(key.endswith("|beroot") for key in scenario_keys))
            self.assertTrue(any(key.endswith("|none") for key in scenario_keys))
            md = format_master_markdown(master)
            self.assertIn("| Tools |", md)

    def test_collaborative_merge_same_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for idx in ("a", "b"):
                run_dir = root / f"run-{idx}"
                run_dir.mkdir()
                (run_dir / "result.json").write_text(
                    json.dumps(_sample_run_doc(run_id=f"run-{idx}")), encoding="utf-8"
                )
            master = build_master_document(root)
            self.assertEqual(master["source_runs_deduped"], 2)
            profiles = master["aggregate"]["by_profile"]
            self.assertEqual(len(profiles), 1)
            only = next(iter(profiles.values()))
            self.assertEqual(only["observations"], 2)
            self.assertEqual(only["runs"], 2)

    def test_different_hardware_stays_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for idx, gpu in enumerate(["GPU-A", "GPU-B"], start=1):
                run_dir = root / f"run-{idx}"
                run_dir.mkdir()
                doc = _sample_run_doc(run_id=f"run-{idx}")
                doc["hardware"] = {
                    "gpu_name": gpu,
                    "gpu_vram": 12282,
                    "cuda_version": "13.1",
                }
                (run_dir / "result.json").write_text(json.dumps(doc), encoding="utf-8")
            master = build_master_document(root)
            self.assertEqual(len(master["aggregate"]["by_profile"]), 2)
            self.assertEqual(master["aggregate"]["overall"]["observations"], 2)

    def test_build_result_document_tools(self):
        from ramigpt.benchmark.results import build_result_document

        doc = build_result_document(
            {"id": "x", "tools": {"beroot": True}, "targets": []},
            settings={"provider": "ollama", "model": "qwen3:14b"},
        )
        self.assertEqual(doc["tools"], ["beroot"])
        self.assertTrue(doc["tools_configured"]["beroot"])


if __name__ == "__main__":
    unittest.main()
