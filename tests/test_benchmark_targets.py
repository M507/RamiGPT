"""Tests for benchmark target-selection profiles."""

from __future__ import annotations

import unittest

from ramigpt.benchmark.targets import (
    DEFAULT_TARGET_PROFILE_ID,
    FAMILY_SUDO,
    FAMILY_SUDO_ADVANCED,
    PROFILES,
    TARGETS,
    get_default_target_ids,
    get_profile,
    list_profiles,
    resolve_profile_for_target_ids,
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

    def test_regression_sample_covers_major_families(self):
        sample = set(self.profiles_by_id["regression-sample"].target_ids)
        families = {self.targets_by_id[tid].family for tid in sample}
        self.assertIn(FAMILY_SUDO, families)
        self.assertIn("suid", families)
        self.assertIn("writable", families)
        self.assertIn("credentials", families)
        self.assertGreaterEqual(len(sample), 15)

    def test_non_sudo_excludes_frozen_sudo_families(self):
        ids = self.profiles_by_id["non-sudo"].target_ids
        families = {self.targets_by_id[tid].family for tid in ids}
        self.assertNotIn(FAMILY_SUDO, families)
        self.assertNotIn(FAMILY_SUDO_ADVANCED, families)
        self.assertEqual(len(ids), 197)

    def test_detect_only_profile_matches_registry(self):
        expected = [target.id for target in TARGETS if not target.expects_root]
        self.assertEqual(self.profiles_by_id["detect-only"].target_ids, expected)
        self.assertEqual(len(expected), 17)

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

    def test_default_profile_is_regression_sample(self):
        self.assertEqual(DEFAULT_TARGET_PROFILE_ID, "regression-sample")
        default_ids = get_default_target_ids()
        self.assertEqual(
            default_ids,
            self.profiles_by_id["regression-sample"].target_ids,
        )
        self.assertGreaterEqual(len(default_ids), 15)

    def test_resolve_profile_for_exact_target_selection(self):
        sample_ids = self.profiles_by_id["does-it-work"].target_ids
        profile = resolve_profile_for_target_ids(sample_ids)
        self.assertIsNotNone(profile)
        self.assertEqual(profile.id, "does-it-work")
        self.assertIsNone(resolve_profile_for_target_ids(["sudo-vim", "sudo-awk"]))

    def test_profile_ids_are_unique_and_grouped(self):
        ids = [profile.id for profile in PROFILES]
        self.assertEqual(len(ids), len(set(ids)))
        groups = {profile.group for profile in PROFILES}
        self.assertTrue({"Quick runs", "Themed runs", "Full families"}.issubset(groups))

    def test_serialized_profiles_include_ui_fields(self):
        serialized = list_profiles()
        self.assertEqual(len(serialized), len(PROFILES))
        self.assertEqual(
            set(serialized[0]),
            {"id", "name", "description", "target_ids", "group"},
        )
        self.assertEqual(get_profile("regression-sample").group, "Quick runs")


if __name__ == "__main__":
    unittest.main()
