"""Tests for AI token-usage capture in logs and benchmark results."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from ramigpt.ai import service as svc
from ramigpt.ai.providers.compat import usage_from_completion
from ramigpt.ai.providers.ollama_provider import OllamaProvider
from ramigpt.benchmark.results import (
    BENCHMARK_RESULT_SCHEMA_VERSION,
    _format_target_timing_summary,
    build_result_document,
    enrich_target_from_events,
)
from ramigpt.config import Settings
from ramigpt.utils.session_logging import SessionLogger


class UsageExtractionTests(unittest.TestCase):
    def test_object_style_usage(self):
        completion = SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=120, completion_tokens=30, total_tokens=150)
        )
        self.assertEqual(
            usage_from_completion(completion),
            {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150},
        )

    def test_dict_style_usage_without_total(self):
        completion = SimpleNamespace(usage={"prompt_tokens": 50, "completion_tokens": 10})
        self.assertEqual(
            usage_from_completion(completion),
            {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
        )

    def test_missing_usage_returns_none(self):
        self.assertIsNone(usage_from_completion(SimpleNamespace()))
        self.assertIsNone(usage_from_completion(SimpleNamespace(usage=SimpleNamespace())))


class ProviderUsageCaptureTests(unittest.TestCase):
    def test_ollama_provider_sets_last_usage(self):
        class FakeCompletions:
            def create(self, model, messages):
                msg = SimpleNamespace(content="sudo id", model_extra={})
                choice = SimpleNamespace(message=msg)
                usage = SimpleNamespace(
                    prompt_tokens=200, completion_tokens=15, total_tokens=215
                )
                return SimpleNamespace(choices=[choice], usage=usage)

        class FakeClient:
            chat = SimpleNamespace(completions=FakeCompletions())

        settings = Settings(
            ai_provider="ollama",
            ollama_base_url="http://localhost:11434",
            ollama_model="qwen3:14b",
        )
        provider = OllamaProvider(settings, client=FakeClient())
        text = provider.create_completion(
            [{"role": "system", "content": "sys"}, {"role": "user", "content": "go"}]
        )
        self.assertEqual(text, "sudo id")
        self.assertEqual(
            provider.last_usage,
            {"prompt_tokens": 200, "completion_tokens": 15, "total_tokens": 215},
        )

    def test_get_answer_with_usage_returns_provider_usage(self):
        class FakeProvider:
            def create_completion(self, messages):
                self.last_usage = {
                    "prompt_tokens": 300,
                    "completion_tokens": 20,
                    "total_tokens": 320,
                }
                return "id"

        with mock.patch.object(svc, "create_provider", return_value=FakeProvider()):
            text, usage = svc.get_answer_with_usage("sys", "prompt")
        self.assertEqual(text, "id")
        self.assertEqual(usage["total_tokens"], 320)


class SessionLoggerTokenTests(unittest.TestCase):
    def test_ai_turn_persists_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            slog = SessionLogger("test-sid", session_dir=Path(tmp))
            slog.begin_run("connect")
            slog.ai_turn(
                request_n=1,
                system="sys",
                prompt="p" * 10,
                raw_response="sudo id",
                filtered_command="sudo id",
                provider="ollama",
                model="qwen3:14b",
                usage={"prompt_tokens": 500, "completion_tokens": 25, "total_tokens": 525},
            )
            lines = slog.events_path.read_text().splitlines()
            ev = json.loads(lines[-1])
            self.assertEqual(ev["details"]["prompt_tokens"], 500)
            self.assertEqual(ev["details"]["completion_tokens"], 25)
            self.assertEqual(ev["details"]["total_tokens"], 525)

            session_txt = (slog.run_dir / "session.log").read_text()
            self.assertIn("tokens: 525", session_txt)

    def test_ai_turn_without_usage_omits_token_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            slog = SessionLogger("test-sid-2", session_dir=Path(tmp))
            slog.begin_run("connect")
            slog.ai_turn(
                request_n=1,
                system="sys",
                prompt="p",
                raw_response="id",
                filtered_command="id",
            )
            lines = slog.events_path.read_text().splitlines()
            ev = json.loads(lines[-1])
            self.assertIsNone(ev["details"]["total_tokens"])
            session_txt = (slog.run_dir / "session.log").read_text()
            self.assertNotIn("tokens:", session_txt)


class BenchmarkTokenAggregationTests(unittest.TestCase):
    def test_enrich_and_summary_totals(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite_dir = Path(tmp)
            target_dir = suite_dir / "sudo-awk" / "001_run"
            target_dir.mkdir(parents=True)
            events = [
                {"kind": "FULL_AI_START", "details": {"provider": "ollama", "model": "qwen3:14b"}},
                {
                    "kind": "AI_TURN",
                    "details": {
                        "filtered_command": "id",
                        "provider": "ollama",
                        "model": "qwen3:14b",
                        "prompt_tokens": 400,
                        "completion_tokens": 10,
                        "total_tokens": 410,
                    },
                },
                {
                    "kind": "AI_TURN",
                    "details": {
                        "filtered_command": "sudo awk 'BEGIN{system(\"id\")}'",
                        "provider": "ollama",
                        "model": "qwen3:14b",
                        "prompt_tokens": 600,
                        "completion_tokens": 20,
                        "total_tokens": 620,
                    },
                },
                {
                    "kind": "FULL_AI_END",
                    "details": {
                        "requests_run": 2,
                        "got_root": True,
                        "provider": "ollama",
                        "model": "qwen3:14b",
                    },
                },
            ]
            (target_dir / "events.jsonl").write_text(
                "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
            )

            item = {"target_id": "sudo-awk", "status": "passed"}
            out = enrich_target_from_events(item, str(suite_dir))
            self.assertEqual(out["prompt_tokens"], 1000)
            self.assertEqual(out["completion_tokens"], 30)
            self.assertEqual(out["tokens_total"], 1030)

            run_public = {
                "id": "run1",
                "targets": [out],
                "log_dir": str(suite_dir),
                "phase": "done",
                "mode": "test",
                "host": "h",
            }
            doc = build_result_document(run_public)
            self.assertEqual(doc["summary"]["tokens_total"], 1030)
            self.assertEqual(doc["summary"]["prompt_tokens_total"], 1000)
            self.assertEqual(doc["summary"]["completion_tokens_total"], 30)

    def test_no_token_data_omits_totals_gracefully(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite_dir = Path(tmp)
            target_dir = suite_dir / "sudo-vim" / "001_run"
            target_dir.mkdir(parents=True)
            events = [
                {"kind": "AI_TURN", "details": {"filtered_command": "id"}},
                {"kind": "FULL_AI_END", "details": {"requests_run": 1, "got_root": False}},
            ]
            (target_dir / "events.jsonl").write_text(
                "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
            )
            item = {"target_id": "sudo-vim", "status": "failed"}
            out = enrich_target_from_events(item, str(suite_dir))
            self.assertIsNone(out.get("tokens_total"))

            run_public = {
                "id": "run2",
                "targets": [out],
                "log_dir": str(suite_dir),
                "phase": "done",
                "mode": "test",
                "host": "h",
            }
            doc = build_result_document(run_public)
            self.assertEqual(doc["summary"]["tokens_total"], 0)

    def test_timing_breakdown_from_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite_dir = Path(tmp)
            target_dir = suite_dir / "sudo-vim" / "001_run"
            target_dir.mkdir(parents=True)
            events = [
                {
                    "ts": "2026-07-18T15:00:00+00:00",
                    "kind": "BEROOT_START",
                    "details": {"with_ai": True},
                },
                {
                    "ts": "2026-07-18T15:00:45+00:00",
                    "kind": "BEROOT_OK",
                    "details": {"duration_seconds": 45.0, "with_ai": True},
                },
                {
                    "ts": "2026-07-18T15:00:46+00:00",
                    "kind": "FULL_AI_START",
                    "details": {"provider": "ollama", "model": "qwen3:14b"},
                },
                {
                    "ts": "2026-07-18T15:00:55+00:00",
                    "kind": "AI_TURN",
                    "details": {
                        "request_n": 1,
                        "filtered_command": "sudo vim",
                        "duration_seconds": 8.5,
                        "prompt_tokens": 100,
                        "completion_tokens": 20,
                        "total_tokens": 120,
                    },
                },
                {
                    "ts": "2026-07-18T15:00:57+00:00",
                    "kind": "SHELL_IO",
                    "details": {
                        "request_n": 1,
                        "command": "sudo vim",
                        "duration_seconds": 2.0,
                    },
                },
                {
                    "ts": "2026-07-18T15:01:00+00:00",
                    "kind": "FULL_AI_END",
                    "details": {"requests_run": 1, "got_root": True},
                },
            ]
            (target_dir / "events.jsonl").write_text(
                "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
            )
            item = {
                "target_id": "sudo-vim",
                "status": "passed",
                "elapsed_seconds": 60.0,
            }
            out = enrich_target_from_events(item, str(suite_dir))
            self.assertEqual(out["timing_summary"]["beroot_seconds"], 45.0)
            self.assertEqual(out["timing_summary"]["ai_llm_seconds"], 8.5)
            self.assertEqual(out["timing_summary"]["shell_seconds"], 2.0)
            self.assertEqual(len(out["ai_turns"]), 1)
            self.assertEqual(out["ai_turns"][0]["shell_duration_seconds"], 2.0)
            self.assertEqual(out["tool_runs"][0]["tool"], "beroot")

            doc = build_result_document(
                {
                    "id": "run3",
                    "targets": [out],
                    "log_dir": str(suite_dir),
                    "phase": "done",
                    "mode": "test",
                    "host": "h",
                }
            )
            self.assertEqual(doc["schema_version"], BENCHMARK_RESULT_SCHEMA_VERSION)
            self.assertEqual(doc["summary"]["beroot_seconds_total"], 45.0)
            self.assertEqual(doc["summary"]["ai_llm_seconds_total"], 8.5)
            self.assertEqual(doc["summary"]["shell_seconds_total"], 2.0)
            summary_txt = "\n".join(_format_target_timing_summary(out))
            self.assertIn("beroot=45.0s", summary_txt)
            self.assertIn("ai #1:", summary_txt)
            self.assertIn("llm=8.5s", summary_txt)

    def test_result_issues_when_events_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite_dir = Path(tmp)
            item = {"target_id": "sudo-vim", "status": "passed", "elapsed_seconds": 10.0}
            out = enrich_target_from_events(item, str(suite_dir))
            self.assertTrue(out.get("issues"))
            self.assertIn("no events.jsonl", out["issues"][0])

    def test_diagnose_flags_missing_ai_timing(self):
        with tempfile.TemporaryDirectory() as tmp:
            suite_dir = Path(tmp)
            target_dir = suite_dir / "sudo-awk" / "001_run"
            target_dir.mkdir(parents=True)
            events = [
                {
                    "ts": "2026-07-18T15:00:55+00:00",
                    "kind": "AI_TURN",
                    "details": {
                        "request_n": 1,
                        "filtered_command": "id",
                    },
                },
            ]
            (target_dir / "events.jsonl").write_text(
                "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
            )
            item = {"target_id": "sudo-awk", "status": "failed", "elapsed_seconds": 5.0}
            out = enrich_target_from_events(item, str(suite_dir))
            joined = "\n".join(out.get("issues") or [])
            self.assertIn("missing llm_duration_seconds", joined)
            self.assertIn("missing token usage", joined)
            self.assertIn("FULL_AI_END missing", joined)


if __name__ == "__main__":
    unittest.main()
