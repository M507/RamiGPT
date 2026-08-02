"""Ensure benchmark targets stay aligned across app, docker, and verify checks."""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from ramigpt.benchmark.targets import PROFILES, TARGETS
from ramigpt.benchmark.verify import write_catalog
from ramigpt.paths import PROJECT_ROOT

CHECKS_DIR = PROJECT_ROOT / "scripts" / "benchmark" / "checks"
CATALOG_PATH = CHECKS_DIR / "catalog.tsv"
COMPOSE_PATH = PROJECT_ROOT / "docker" / "benchmark" / "docker-compose.yml"
APPLY_PATH = PROJECT_ROOT / "docker" / "benchmark" / "apply-misconfig.sh"


def _parse_compose_services() -> dict[str, dict[str, str | int]]:
    text = COMPOSE_PATH.read_text(encoding="utf-8")
    services: dict[str, dict[str, str | int]] = {}
    current: str | None = None
    for line in text.splitlines():
        match = re.match(r"^\s+(bench-[a-z0-9-]+):\s*$", line)
        if match:
            current = match.group(1).replace("bench-", "")
            services[current] = {}
            continue
        if not current:
            continue
        port_match = re.search(r'SSH_PORT:\s*"?(\d+)"?', line)
        if port_match:
            services[current]["port"] = int(port_match.group(1))
        misconfig_match = re.search(r'MISCONFIG:\s*"?([^"\n]+)"?', line)
        if misconfig_match:
            services[current]["misconfig"] = misconfig_match.group(1)
    return services


def _parse_catalog() -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    for line in CATALOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        target_id, port, expects_root, script = line.split("\t", 3)
        rows[target_id] = {
            "port": int(port),
            "expects_root": expects_root == "1",
            "script": script,
        }
    return rows


def _misconfig_supported(misconfig: str, apply_text: str) -> bool:
    if not misconfig:
        return True
    prefix_cases = (
        "sudo:",
        "suid:",
        "cap-setuid:",
        "cap-dac-read:",
        "cap-chown:",
        "cap-dac-override:",
        "cap-fowner:",
        "cap-fsetid:",
        "cap-setfcap:",
        "cap-net-bind:",
        "writable:",
        "sudo-ld-preload:",
    )
    for prefix in prefix_cases:
        if misconfig.startswith(prefix):
            return True
    return misconfig in apply_text


class BenchmarkRegistryTests(unittest.TestCase):
    def setUp(self):
        self.targets_by_id = {target.id: target for target in TARGETS}
        self.compose = _parse_compose_services()
        self.catalog = _parse_catalog()
        self.apply_text = APPLY_PATH.read_text(encoding="utf-8")

    def test_suite_has_expected_target_count(self):
        self.assertEqual(len(TARGETS), 285)

    def test_catalog_matches_targets(self):
        self.assertEqual(set(self.catalog), set(self.targets_by_id))
        for target in TARGETS:
            row = self.catalog[target.id]
            self.assertEqual(row["port"], target.port)
            self.assertEqual(row["expects_root"], target.expects_root)
            self.assertEqual(row["script"], target.verify_script or f"{target.id}.sh")

    def test_on_disk_catalog_matches_generator(self):
        with tempfile.TemporaryDirectory() as tmp:
            generated = Path(tmp) / "catalog.tsv"
            write_catalog(generated)
            self.assertEqual(
                generated.read_text(encoding="utf-8"),
                CATALOG_PATH.read_text(encoding="utf-8"),
            )

    def test_check_scripts_exist_for_every_target(self):
        for target in TARGETS:
            script = CHECKS_DIR / (target.verify_script or f"{target.id}.sh")
            with self.subTest(target=target.id):
                self.assertTrue(script.is_file(), f"missing {script.name}")
                text = script.read_text(encoding="utf-8")
                self.assertIn("_common.sh", text)

    def test_compose_services_match_targets(self):
        self.assertEqual(set(self.compose), set(self.targets_by_id))
        for target in TARGETS:
            service = self.compose[target.id]
            with self.subTest(target=target.id):
                self.assertEqual(service.get("port"), target.port)
                self.assertEqual(service.get("misconfig"), target.misconfig)

    def test_apply_misconfig_supports_every_target(self):
        for target in TARGETS:
            with self.subTest(target=target.id):
                self.assertTrue(
                    _misconfig_supported(target.misconfig, self.apply_text),
                    target.misconfig,
                )

    def test_ports_are_unique_and_in_band(self):
        seen: set[int] = set()
        for target in TARGETS:
            with self.subTest(target=target.id):
                self.assertGreaterEqual(target.port, 2170)
                self.assertLessEqual(target.port, 2454)
                self.assertNotIn(target.port, seen)
                seen.add(target.port)

    def test_profiles_cover_every_target(self):
        covered = {target_id for profile in PROFILES for target_id in profile.target_ids}
        self.assertEqual(covered, set(self.targets_by_id))

    def test_profile_count_matches_ui_presets(self):
        self.assertEqual(len(PROFILES), 34)


if __name__ == "__main__":
    unittest.main()
