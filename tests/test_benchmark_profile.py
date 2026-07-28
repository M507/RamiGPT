"""Tests for collaborative profile identity helpers."""

from __future__ import annotations

import unittest

from ramigpt.benchmark.profile import (
    collaborative_profile_key,
    profile_display_label,
)


class BenchmarkProfileTests(unittest.TestCase):
    def test_profile_display_label_combines_model_and_hardware(self):
        hardware = {
            "gpu_name": "NVIDIA GeForce RTX 4070",
            "gpu_vram": 12282,
            "cuda_version": "13.1",
        }
        model_key = "ollama-qwen3-14b-example"
        label = profile_display_label(model_key, hardware)
        self.assertIn(model_key, label)
        self.assertIn("RTX 4070", label)
        self.assertIn("12282 MiB", label)

    def test_collaborative_profile_key_merges_matching_inputs(self):
        hardware = {
            "gpu_name": "NVIDIA GeForce RTX 4070",
            "gpu_vram": 12282,
            "cuda_version": "13.1",
        }
        key_a = collaborative_profile_key("model-a", "ollama", "qwen3:14b", hardware)
        key_b = collaborative_profile_key("model-a", "ollama", "qwen3:14b", hardware)
        self.assertEqual(key_a, key_b)
        self.assertTrue(key_a.startswith("model-a|"))

    def test_different_hardware_produces_different_profile_keys(self):
        model_key = "model-a"
        hw_a = {"gpu_name": "GPU-A", "gpu_vram": 8192}
        hw_b = {"gpu_name": "GPU-B", "gpu_vram": 8192}
        self.assertNotEqual(
            collaborative_profile_key(model_key, "ollama", "qwen3:14b", hw_a),
            collaborative_profile_key(model_key, "ollama", "qwen3:14b", hw_b),
        )


if __name__ == "__main__":
    unittest.main()
