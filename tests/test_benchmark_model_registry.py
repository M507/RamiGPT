"""Tests for benchmark model registry key_name generation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ramigpt.benchmark.model_registry import (
    build_ollama_fingerprint,
    ensure_model_registry_entry,
    fingerprint_to_key_name,
    parse_modelfile_parameters,
)
from ramigpt.config.settings import Settings


class BenchmarkModelRegistryTests(unittest.TestCase):
    def test_parse_modelfile_parameters(self):
        text = "FROM qwen3:14b\nPARAMETER num_ctx 8192\nPARAMETER temperature 0.6\n"
        params = parse_modelfile_parameters(text)
        self.assertEqual(params["num_ctx"], "8192")
        self.assertEqual(params["temperature"], "0.6")

    def test_fingerprint_to_key_name_ollama(self):
        fp = {
            "provider": "ollama",
            "model": "qwen3:14b",
            "family": "qwen3",
            "parameter_size": "14.8B",
            "quantization_level": "Q4_K_M",
            "digest": "sha256:abcdef0123456789",
        }
        key = fingerprint_to_key_name(fp)
        self.assertTrue(key.startswith("ollama-qwen3-14b"))
        self.assertIn("q4_k_m", key)
        self.assertIn("sha256abcdef", key)

    def test_same_tag_different_parameters_get_different_keys(self):
        base = {
            "provider": "ollama",
            "model": "qwen3:14b",
            "family": "qwen3",
            "parameter_size": "14.8B",
            "quantization_level": "Q4_K_M",
        }
        fp_a = {**base, "parameters": {"num_ctx": "4096"}}
        fp_b = {**base, "parameters": {"num_ctx": "8192"}}
        self.assertNotEqual(fingerprint_to_key_name(fp_a), fingerprint_to_key_name(fp_b))

    def test_fingerprint_to_key_name_openwebui_ignores_base_url(self):
        fp_a = {
            "provider": "openwebui",
            "model": "qwen3:14b",
            "base_url": "http://10.10.10.82:8080",
        }
        fp_b = {
            "provider": "openwebui",
            "model": "qwen3:14b",
            "base_url": "http://other-host:8080",
        }
        self.assertEqual(fingerprint_to_key_name(fp_a), "openwebui-qwen3-14b")
        self.assertEqual(fingerprint_to_key_name(fp_a), fingerprint_to_key_name(fp_b))

    @patch("ramigpt.benchmark.model_registry.fetch_ollama_tag_info")
    @patch("ramigpt.benchmark.model_registry.fetch_ollama_show")
    def test_ensure_model_registry_entry_writes_json(self, mock_show, mock_tag):
        mock_show.return_value = {
            "modelfile": "PARAMETER num_ctx 8192\n",
            "details": {
                "family": "qwen3",
                "parameter_size": "14.8B",
                "quantization_level": "Q4_K_M",
                "format": "gguf",
            },
        }
        mock_tag.return_value = {"digest": "sha256:deadbeefcafebabe", "size": 9000000000}
        settings = Settings(
            ai_provider="ollama",
            ollama_base_url="http://127.0.0.1:11434",
            ollama_model="qwen3:14b",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entry = ensure_model_registry_entry(settings, models_dir=root)
            self.assertTrue(entry["key_name"])
            path = root / f"{entry['key_name']}.json"
            self.assertTrue(path.is_file())
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["model"], "qwen3:14b")
            self.assertEqual(saved["fingerprint"]["parameter_size"], "14.8B")


if __name__ == "__main__":
    unittest.main()
