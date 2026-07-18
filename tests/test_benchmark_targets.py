"""Tests for benchmark target-selection profiles."""

from __future__ import annotations

import unittest

from ramigpt.benchmark.targets import (
    FAMILY_SUDO,
    FAMILY_SUDO_ADVANCED,
    PROFILES,
    TARGETS,
    list_profiles,
)


class BenchmarkTargetProfileTests(unittest.TestCase):
    def setUp(self):
        self.targets_by_id = {target.id: target for target in TARGETS}
        self.profiles_by_id = {profile.id: profile for profile in PROFILES}

    def test_does_it_work_profile_has_requested_targets(self):
        self.assertEqual(
            self.profiles_by_id["does-it-work"].target_ids,
            ["sudo-vim", "sudo-all", "sudo-awk"],
        )

    def test_all_sudo_profile_contains_every_sudo_target(self):
        expected = [
            target.id
            for target in TARGETS
            if target.family in {FAMILY_SUDO, FAMILY_SUDO_ADVANCED}
        ]
        self.assertEqual(self.profiles_by_id["all-sudo-problems"].target_ids, expected)

    def test_profiles_only_reference_known_targets_without_duplicates(self):
        for profile in PROFILES:
            with self.subTest(profile=profile.id):
                self.assertTrue(profile.target_ids)
                self.assertEqual(len(profile.target_ids), len(set(profile.target_ids)))
                self.assertTrue(set(profile.target_ids).issubset(self.targets_by_id))

    def test_serialized_profiles_include_ui_fields(self):
        serialized = list_profiles()
        self.assertEqual(len(serialized), len(PROFILES))
        self.assertEqual(
            set(serialized[0]),
            {"id", "name", "description", "target_ids"},
        )


if __name__ == "__main__":
    unittest.main()
