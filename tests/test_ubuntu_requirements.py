"""Tests for Ubuntu host requirements helper."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from ramigpt.utils.ubuntu_requirements import (
    AptRequirement,
    check_ansible_core_version,
    check_apt_requirements,
    ensure_ubuntu_requirements,
    is_debian_like,
    is_requirement_present,
    read_os_release,
    reset_ubuntu_requirements_cache,
)


class UbuntuRequirementsTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_ubuntu_requirements_cache()

    def test_is_debian_like_ubuntu(self):
        self.assertTrue(is_debian_like({"ID": "ubuntu", "ID_LIKE": "debian"}))
        self.assertTrue(is_debian_like({"ID": "linuxmint", "ID_LIKE": "ubuntu debian"}))
        self.assertFalse(is_debian_like({"ID": "fedora", "ID_LIKE": "rhel"}))

    def test_read_os_release_roundtrip(self):
        if not Path("/etc/os-release").is_file():
            self.skipTest("/etc/os-release missing")
        data = read_os_release()
        self.assertTrue(data.get("ID") or data.get("NAME"))

    def test_requirement_present_by_binary(self):
        req = AptRequirement(package="openssh-client", binaries=("ssh",), reason="ssh")
        present, detail = is_requirement_present(req)
        self.assertTrue(present)
        self.assertIn("ssh", detail)

    @patch("ramigpt.utils.ubuntu_requirements.shutil.which", return_value=None)
    @patch("ramigpt.utils.ubuntu_requirements._dpkg_installed", return_value=False)
    def test_requirement_missing(self, _dpkg, _which):
        req = AptRequirement(package="sshpass", binaries=("sshpass",), reason="pw")
        present, detail = is_requirement_present(req)
        self.assertFalse(present)
        self.assertIn("sshpass", detail)

    @patch.dict("os.environ", {"RAMIGPT_SKIP_UBUNTU_REQUIREMENTS": "1"}, clear=False)
    def test_skip_env(self):
        result = ensure_ubuntu_requirements(force=True)
        self.assertTrue(result.skipped)
        self.assertTrue(result.ok)

    def test_check_apt_requirements_lists_status(self):
        statuses = check_apt_requirements()
        self.assertGreaterEqual(len(statuses), 3)
        names = {s.requirement.package for s in statuses}
        self.assertIn("sshpass", names)
        self.assertIn("openssh-client", names)

    def test_ansible_core_version_in_supported_range(self):
        ok, detail = check_ansible_core_version()
        self.assertTrue(ok, detail)
        self.assertIn("ansible-core", detail)


if __name__ == "__main__":
    unittest.main()
