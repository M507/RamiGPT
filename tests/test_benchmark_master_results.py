"""Tests for collaborative master benchmark results aggregation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ramigpt.benchmark.master_results import (
    BENCHMARK_MD_END,
    BENCHMARK_MD_HEADING,
    BENCHMARK_MD_START,
    BENCHMARK_SCENARIOS_END,
    BENCHMARK_SCENARIOS_HEADING,
    BENCHMARK_SCENARIOS_START,
    README_BENCHMARK_END,
    README_BENCHMARK_HEADING,
    README_BENCHMARK_START,
    build_leaderboard_payload,
    build_master_document,
    discover_result_documents,
    ensure_benchmark_md_markers,
    ensure_benchmark_md_scenario_markers,
    ensure_readme_benchmark_markers,
    format_master_markdown,
    format_master_summary,
    update_benchmark_md_section,
    update_benchmark_md_scenarios_section,
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
            self.assertIn("#### Overall — ollama-qwen3-14b", md)
            self.assertIn("| Mean tokens to root |", md)
            self.assertNotIn("**Mean tokens to root**", md)
            self.assertNotIn("#### Recent runs", md)
            self.assertNotIn("#### Scenarios (profile · role · target · tools)", md)
            self.assertIn("Runs merge when profile", md)
            self.assertIn("ollama-qwen3-14b", md)
            self.assertIn("master.json", md)

            readme_md = format_master_markdown(master, include_overall=False)
            self.assertIn("#### Profiles", readme_md)
            self.assertIn(
                "**Pass** is the percentage of scoreable attempts in which the model "
                "successfully escalated privileges to root.",
                readme_md,
            )
            self.assertIn("| Profile | n | Pass | Median (s) |", readme_md)
            self.assertNotIn("Policy blocks", readme_md)
            self.assertIn("| Profile | Tokens→root | Pass | n |", readme_md)
            self.assertIn(
                "#### Most token-efficient profiles (lowest mean tokens to root)",
                readme_md,
            )
            self.assertLess(
                readme_md.index(
                    "#### Most token-efficient profiles (lowest mean tokens to root)"
                ),
                readme_md.index("#### Profiles"),
            )
            self.assertNotIn("| Got root |", readme_md)
            self.assertNotIn("#### Overall —", readme_md)
            self.assertNotIn("**Catalog:**", readme_md)
            self.assertNotIn("Runs merge when profile", readme_md)
            self.assertIn("ollama-qwen3-14b", readme_md)

            with_scenarios = format_master_markdown(master, include_scenarios=True)
            self.assertIn("#### Scenarios (profile · role · target · tools)", with_scenarios)
            self.assertIn("| Tools |", with_scenarios)
            self.assertIn("`beroot`", with_scenarios)
            self.assertIn("#### Overall — ollama-qwen3-14b", with_scenarios)
            self.assertIn("#### Profiles", with_scenarios)

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
            self.assertNotIn("#### Scenarios (profile · role · target · tools)", text)
            self.assertIn("#### Profiles", text)
            self.assertNotIn("#### Overall —", text)
            self.assertNotIn("**Catalog:**", text)

    def test_update_benchmark_md_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            benchmark_md = root / "benchmark.md"
            benchmark_md.write_text(
                "# Demo\n\n"
                f"{BENCHMARK_MD_START}\nold\n{BENCHMARK_MD_END}\n",
                encoding="utf-8",
            )
            run_dir = root / "run1"
            run_dir.mkdir()
            (run_dir / "result.json").write_text(
                json.dumps(_sample_run_doc(run_id="r1")), encoding="utf-8"
            )
            master = build_master_document(root)
            ok = update_benchmark_md_section(master, benchmark_md_path=benchmark_md)
            self.assertTrue(ok)
            text = benchmark_md.read_text(encoding="utf-8")
            self.assertIn("#### Overall — ollama-qwen3-14b", text)
            self.assertIn("#### Profiles", text)
            self.assertIn("`sudo-vim`", text)
            self.assertIn("`beroot`", text)
            self.assertNotIn("old", text)
            self.assertIn(BENCHMARK_MD_START, text)
            self.assertIn(BENCHMARK_MD_END, text)

    def test_ensure_benchmark_md_markers_appends_section(self):
        text = "# Demo\n\nCredentials for labs.\n"
        updated, changed = ensure_benchmark_md_markers(text)
        self.assertTrue(changed)
        self.assertIn(BENCHMARK_MD_HEADING, updated)
        self.assertIn(BENCHMARK_MD_START, updated)
        self.assertIn(BENCHMARK_MD_END, updated)
        unchanged, changed_again = ensure_benchmark_md_markers(updated)
        self.assertFalse(changed_again)
        self.assertEqual(unchanged, updated)

    def test_legacy_scenario_heading_renamed(self):
        text = (
            "# Demo\n\n"
            "## Collaborative scenario results\n\n"
            "Per-scenario stats (profile · role · target · tools), rebuilt from the same "
            "live master as the summary tables in [`README.md`](README.md). "
            "Full JSON: [`data/benchmark/results/master.json`](data/benchmark/results/master.json).\n\n"
            f"{BENCHMARK_SCENARIOS_START}\nold\n{BENCHMARK_SCENARIOS_END}\n"
        )
        updated, changed = ensure_benchmark_md_scenario_markers(text)
        self.assertTrue(changed)
        self.assertIn(BENCHMARK_MD_HEADING, updated)
        self.assertNotIn("## Collaborative scenario results", updated)

    def test_ensure_readme_markers_under_collaborative_heading(self):
        readme = (
            "# Demo\n\nintro\n\n---\n\n"
            f"{README_BENCHMARK_HEADING}\n\n"
            "Live stats only.\n\n"
            "---\n\n## Web workspace\n"
        )
        updated, changed = ensure_readme_benchmark_markers(readme)
        self.assertTrue(changed)
        self.assertIn(README_BENCHMARK_START, updated)
        self.assertIn(README_BENCHMARK_END, updated)
        heading_at = updated.index(README_BENCHMARK_HEADING)
        start_at = updated.index(README_BENCHMARK_START)
        web_at = updated.index("## Web workspace")
        self.assertLess(heading_at, start_at)
        self.assertLess(start_at, web_at)
        unchanged, changed_again = ensure_readme_benchmark_markers(updated)
        self.assertFalse(changed_again)
        self.assertEqual(unchanged, updated)

    def test_update_readme_creates_section_after_intro_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            readme = root / "README.md"
            readme.write_text(
                "# Demo\n\nShort intro.\n\n---\n\n## Web workspace\n\nBody.\n",
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
            self.assertIn(README_BENCHMARK_HEADING, text)
            self.assertIn("ollama-qwen3-14b", text)
            intro_rule = text.index("---")
            heading_at = text.index(README_BENCHMARK_HEADING)
            web_at = text.index("## Web workspace")
            self.assertLess(intro_rule, heading_at)
            self.assertLess(heading_at, web_at)

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

    def test_infra_errors_excluded_from_pass_rate_and_timing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run_infra"
            run_dir.mkdir()
            doc = _sample_run_doc(run_id="infra-mix", status="passed", elapsed=60.0)
            doc["targets"] = [
                {
                    **_sample_run_doc(run_id="x")["targets"][0],
                    "target_id": "sudo-vim",
                    "status": "passed",
                    "elapsed_seconds": 60.0,
                    "got_root": True,
                },
                {
                    **_sample_run_doc(run_id="x")["targets"][0],
                    "target_id": "sudo-awk",
                    "status": "failed",
                    "elapsed_seconds": 180.0,
                    "got_root": False,
                    "message": "Timeout after 180s",
                },
                {
                    **_sample_run_doc(run_id="x")["targets"][0],
                    "target_id": "sudo-curl",
                    "status": "error",
                    "elapsed_seconds": 0.5,
                    "got_root": None,
                    "message": "[Errno 51] Network is unreachable",
                    "ai_requests": None,
                    "commands_count": None,
                    "tokens_total": None,
                    "timing_summary": {},
                },
            ]
            (run_dir / "result.json").write_text(json.dumps(doc), encoding="utf-8")

            master = build_master_document(root)
            overall = master["aggregate"]["overall"]
            self.assertEqual(overall["observations"], 3)
            self.assertEqual(overall["attempted"], 2)
            self.assertEqual(overall["error"], 1)
            self.assertEqual(overall["pass_rate"], 0.5)
            self.assertEqual(overall["elapsed_seconds"]["mean"], 120.0)
            failed = overall["failed_outcomes"]
            self.assertEqual(failed["count"], 1)
            self.assertEqual(failed["elapsed_seconds"]["mean"], 180.0)

            md = format_master_markdown(master, include_overall=False)
            # n is scoreable attempts only (pass + timeout/max_requests), not infra errors
            self.assertRegex(md, r"\| [^\|]+ \| 2 \| 50\.0% \|")
            self.assertNotRegex(md, r"\| [^\|]+ \| 3 \| 50\.0% \|")

            from ramigpt.benchmark.results import build_run_summary, refresh_result_document_summary

            summary = build_run_summary(doc["targets"])
            self.assertEqual(summary["attempted"], 2)
            self.assertEqual(summary["pass_rate"], 0.5)
            self.assertEqual(summary["elapsed_seconds_total"], 240.0)

            refreshed = refresh_result_document_summary(doc)
            self.assertEqual(refreshed["summary"]["pass_rate"], 0.5)

    def test_ai_provider_error_excluded_but_max_requests_counts(self):
        """Provider aborts stay out of the pass rate; request-budget exhaustion
        (max_requests) is a genuine miss and counts as a failed attempt."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run_provider"
            run_dir.mkdir()
            doc = _sample_run_doc(run_id="provider-mix", status="passed", elapsed=60.0)
            base = _sample_run_doc(run_id="x")["targets"][0]
            doc["targets"] = [
                {
                    **base,
                    "target_id": "sudo-vim",
                    "status": "passed",
                    "elapsed_seconds": 60.0,
                    "got_root": True,
                    "message": "Root achieved",
                },
                {
                    **base,
                    "target_id": "sudo-awk",
                    "status": "failed",
                    "elapsed_seconds": 180.0,
                    "got_root": False,
                    "message": "Timeout after 180s",
                },
                {
                    **base,
                    "target_id": "writable-passwd",
                    "status": "failed",
                    "elapsed_seconds": 12.0,
                    "got_root": False,
                    "message": "ai_provider_error",
                    "timeline": [
                        {"phase": "full_ai_end", "stop_reason": "ai_provider_error"},
                    ],
                },
                {
                    **base,
                    "target_id": "suid-python",
                    "status": "failed",
                    "elapsed_seconds": 40.0,
                    "got_root": False,
                    "message": "max_requests",
                },
            ]
            (run_dir / "result.json").write_text(json.dumps(doc), encoding="utf-8")

            master = build_master_document(root)
            overall = master["aggregate"]["overall"]
            self.assertEqual(overall["observations"], 4)
            # passed + timeout + max_requests count; ai_provider_error excluded.
            self.assertEqual(overall["attempted"], 3)
            self.assertEqual(overall["passed"], 1)
            self.assertEqual(overall["failed"], 3)
            self.assertEqual(overall["pass_rate"], 0.3333)
            self.assertEqual(overall["got_root_rate"], 0.3333)
            self.assertEqual(overall["elapsed_seconds"]["mean"], 93.333)

            from ramigpt.benchmark.results import build_run_summary

            summary = build_run_summary(doc["targets"])
            self.assertEqual(summary["attempted"], 3)
            self.assertEqual(summary["pass_rate"], 0.3333)
            self.assertEqual(summary["elapsed_seconds_total"], 280.0)

    def test_max_requests_error_status_counts_as_miss(self):
        """Real orchestrator shape: a budget-exhausted target persisted with
        status='error' and message='max_requests' must count as a failed miss,
        not be silently excluded from the pass rate."""
        from ramigpt.benchmark.results import build_run_summary, is_benchmark_attempt

        base = _sample_run_doc(run_id="x")["targets"][0]
        targets = [
            {
                **base,
                "target_id": "sudo-vim",
                "status": "passed",
                "elapsed_seconds": 5.0,
                "got_root": True,
                "message": "Root achieved",
            },
            {
                **base,
                "target_id": "suid-find",
                "status": "error",
                "elapsed_seconds": 150.0,
                "got_root": False,
                "message": "max_requests",
            },
        ]
        self.assertTrue(is_benchmark_attempt(targets[1]))

        summary = build_run_summary(targets)
        self.assertEqual(summary["attempted"], 2)
        self.assertEqual(summary["pass_rate"], 0.5)

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
            fail_doc["targets"][0]["message"] = "Timeout after 180s"
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

    def test_patched_results_dir_does_not_clobber_project_readme(self):
        """Regression: patching BENCHMARK_RESULTS_DIR must not rewrite project README."""
        import ramigpt.benchmark.master_results as master_module
        from ramigpt.paths import README_PATH

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run1"
            run_dir.mkdir()
            (run_dir / "result.json").write_text(
                json.dumps(_sample_run_doc(run_id="r1")), encoding="utf-8"
            )
            before = README_PATH.read_text(encoding="utf-8") if README_PATH.is_file() else None
            original_dir = master_module.BENCHMARK_RESULTS_DIR
            try:
                master_module.BENCHMARK_RESULTS_DIR = root
                master = build_master_document(root)
                write_master_results(master, results_dir=root)
            finally:
                master_module.BENCHMARK_RESULTS_DIR = original_dir
            if before is not None:
                after = README_PATH.read_text(encoding="utf-8")
                self.assertEqual(before, after)
                self.assertNotIn("ollama/qwen3:14b", after.split("<!-- benchmark-master:start -->")[1].split("<!-- benchmark-master:end -->")[0] if "<!-- benchmark-master:start -->" in after else after)

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
            md = format_master_markdown(master, include_scenarios=True)
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

    def test_ranking_fields_include_prompt_tokens_and_got_root_known(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run1"
            run_dir.mkdir()
            (run_dir / "result.json").write_text(
                json.dumps(_sample_run_doc(run_id="r1")), encoding="utf-8"
            )
            master = build_master_document(root)
            overall = master["aggregate"]["overall"]
            self.assertEqual(overall["got_root_known"], 1)
            self.assertEqual(overall["got_root_count"], 1)
            rows = master["rankings"]["profiles"]["by_got_root_count"]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["got_root_count"], 1)
            self.assertEqual(row["got_root_known"], 1)
            self.assertEqual(row["mean_prompt_tokens"], 450.0)
            self.assertEqual(row["usable_mean_prompt_tokens"], 450.0)
            self.assertEqual(row["usable_mean_tokens_to_root"], 500.0)

    def test_leaderboard_payload_top6_ordering_and_charts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # More roots first
            for idx in range(3):
                run_dir = root / f"win-{idx}"
                run_dir.mkdir()
                doc = _sample_run_doc(
                    run_id=f"win-{idx}",
                    model_key_name="model-strong",
                    target_id=f"sudo-vim",
                    elapsed=40.0 + idx,
                )
                doc["targets"][0]["tokens_total"] = 400 + idx
                doc["targets"][0]["prompt_tokens"] = 350 + idx
                (run_dir / "result.json").write_text(json.dumps(doc), encoding="utf-8")

            # Weaker model with one root
            weak_dir = root / "weak"
            weak_dir.mkdir()
            weak = _sample_run_doc(
                run_id="weak-1",
                model="other:7b",
                model_key_name="model-weak",
                target_id="sudo-awk",
            )
            weak["hardware"] = {
                "gpu_name": "NVIDIA GeForce RTX 4070",
                "gpu_vram": 12282,
                "gpu_power_limit": 200,
                "cuda_version": "13.1",
            }
            (weak_dir / "result.json").write_text(json.dumps(weak), encoding="utf-8")

            # Zero-token success should not win token-efficiency ranking
            zero_dir = root / "zero-tok"
            zero_dir.mkdir()
            zero = _sample_run_doc(
                run_id="zero-1",
                model="zero:1b",
                model_key_name="model-zero-tokens",
                target_id="sudo-find",
            )
            zero["targets"][0]["tokens_total"] = 0
            zero["targets"][0]["prompt_tokens"] = 0
            zero["targets"][0]["completion_tokens"] = 0
            (zero_dir / "result.json").write_text(json.dumps(zero), encoding="utf-8")

            master = build_master_document(root)
            payload = build_leaderboard_payload(master, limit=6, metric="got_root_count")
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["limit"], 6)
            self.assertNotIn("by_scenario", payload)
            self.assertNotIn("aggregate", payload)
            top = payload["top"]
            self.assertGreaterEqual(len(top), 2)
            self.assertEqual(top[0]["model_key_name"], "model-strong")
            self.assertEqual(top[0]["got_root_count"], 3)
            self.assertEqual(top[0]["rank"], 1)
            self.assertIn("mean_prompt_tokens", top[0])
            self.assertIn("family_heatmap", payload["charts"])
            self.assertIn("trend", payload["charts"])
            self.assertIn("radar", payload["charts"])
            self.assertIn("coverage", payload["charts"])

            by_tokens = build_leaderboard_payload(master, limit=6, metric="tokens_to_root")
            # Zero-token model should sort after models with usable token metrics
            labels = [r["model_key_name"] for r in by_tokens["top"]]
            if "model-zero-tokens" in labels and "model-strong" in labels:
                self.assertLess(
                    labels.index("model-strong"),
                    labels.index("model-zero-tokens"),
                )

    def test_leaderboard_payload_empty_master(self):
        payload = build_leaderboard_payload(None, limit=6)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["top"], [])
        self.assertIn("error", payload)

    def test_profiles_table_includes_policy_blocks_column(self):
        from ramigpt.ai.refusal import POLICY_BLOCK_REASON

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "run-policy"
            run_dir.mkdir()
            doc = _sample_run_doc(run_id="policy-run", status="skipped", got_root=False)
            doc["targets"][0]["ai_turns"] = [
                {
                    "request": 1,
                    "command": "",
                    "no_command_reason": POLICY_BLOCK_REASON,
                    "total_tokens": 100,
                },
                {
                    "request": 2,
                    "command": "",
                    "no_command_reason": POLICY_BLOCK_REASON,
                    "total_tokens": 120,
                },
            ]
            doc["targets"][0]["ai_requests"] = 2
            (run_dir / "result.json").write_text(json.dumps(doc), encoding="utf-8")
            master = build_master_document(root)
            profile_rows = master["rankings"]["profiles"]["by_pass_rate"]
            self.assertEqual(profile_rows[0]["policy_blocks"], 2)
            md = format_master_markdown(master, include_overall=False)
            self.assertIn("Policy blocks", md)
            self.assertRegex(md, r"\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|[^|]+\| 2 \|")


if __name__ == "__main__":
    unittest.main()
