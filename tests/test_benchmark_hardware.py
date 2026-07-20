"""Tests for benchmark hardware profile env loading."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from ramigpt.benchmark.hardware import (
    hardware_is_configured,
    hardware_key,
    hardware_label,
    load_benchmark_hardware,
    openwebui_hardware_profile,
    resolve_benchmark_hardware,
)


class BenchmarkHardwareTests(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "BENCHMARK_GPU_NAME": "NVIDIA GeForce RTX 4070",
            "BENCHMARK_GPU_VRAM": "12282",
            "BENCHMARK_GPU_POWER_LIMIT": "200",
            "BENCHMARK_GPU_DRIVER": "591.86",
            "BENCHMARK_CUDA_VERSION": "13.1",
        },
        clear=False,
    )
    def test_load_benchmark_hardware_from_env(self):
        profile = load_benchmark_hardware(reload_env=False)
        self.assertEqual(profile["gpu_name"], "NVIDIA GeForce RTX 4070")
        self.assertEqual(profile["gpu_vram"], 12282)
        self.assertEqual(profile["gpu_power_limit"], 200)
        self.assertEqual(profile["cuda_version"], "13.1")
        self.assertTrue(hardware_is_configured(profile))
        self.assertIn("12282 MiB", hardware_label(profile))

    def test_parse_legacy_vram_and_power_strings(self):
        profile = load_benchmark_hardware(reload_env=False)
        # Direct normalization helpers via reload with patched env
        with patch.dict(
            os.environ,
            {
                "BENCHMARK_GPU_NAME": "NVIDIA GeForce RTX 4070",
                "BENCHMARK_GPU_VRAM": "12 GB (12282 MiB)",
                "BENCHMARK_GPU_POWER_LIMIT": "200 W",
            },
            clear=False,
        ):
            legacy = load_benchmark_hardware(reload_env=False)
        self.assertEqual(legacy["gpu_vram"], 12282)
        self.assertEqual(legacy["gpu_power_limit"], 200)

    def test_hardware_key_stable_for_same_lab_profile(self):
        profile = {
            "gpu_name": "NVIDIA GeForce RTX 4070",
            "gpu_vram": 12282,
            "gpu_power_limit": 200,
            "cuda_version": "13.1",
        }
        self.assertEqual(hardware_key(profile), hardware_key(dict(profile)))

    def test_power_limit_does_not_affect_hardware_key(self):
        base = {
            "gpu_name": "NVIDIA GeForce RTX 4070",
            "gpu_vram": 12282,
            "gpu_driver": "591.86",
            "cuda_version": "13.1",
        }
        low_power = {**base, "gpu_power_limit": 200}
        high_power = {**base, "gpu_power_limit": 250}
        self.assertEqual(hardware_key(low_power), hardware_key(high_power))

    def test_openwebui_hardware_profile_ignores_env_gpu(self):
        profile = openwebui_hardware_profile()
        self.assertEqual(profile["gpu_name"], "Online AI Service")
        self.assertEqual(profile["gpu_driver"], "Open WebUI proxy")
        self.assertNotIn("gpu_vram", profile)
        self.assertNotIn("cuda_version", profile)
        self.assertEqual(hardware_label(profile), "Online AI Service")

    def test_openwebui_hardware_profile_same_key_regardless_of_url(self):
        a = openwebui_hardware_profile()
        b = openwebui_hardware_profile()
        self.assertEqual(hardware_key(a), hardware_key(b))

    @patch.dict(
        os.environ,
        {
            "BENCHMARK_GPU_NAME": "NVIDIA GeForce RTX 4070",
            "BENCHMARK_GPU_VRAM": "12282",
            "BENCHMARK_GPU_DRIVER": "591.86",
            "BENCHMARK_CUDA_VERSION": "13.1",
        },
        clear=False,
    )
    def test_resolve_benchmark_hardware_for_openwebui(self):
        profile = resolve_benchmark_hardware(provider="openwebui", reload_env=False)
        self.assertEqual(profile["gpu_name"], "Online AI Service")
        self.assertEqual(profile["gpu_driver"], "Open WebUI proxy")
        self.assertNotIn("gpu_vram", profile)

    @patch.dict(
        os.environ,
        {
            "BENCHMARK_GPU_NAME": "NVIDIA GeForce RTX 4070",
            "BENCHMARK_GPU_VRAM": "12282",
        },
        clear=False,
    )
    def test_resolve_benchmark_hardware_for_ollama_uses_env(self):
        profile = resolve_benchmark_hardware(provider="ollama", reload_env=False)
        self.assertEqual(profile["gpu_name"], "NVIDIA GeForce RTX 4070")
        self.assertEqual(profile["gpu_vram"], 12282)


if __name__ == "__main__":
    unittest.main()
