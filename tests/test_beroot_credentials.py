"""Tests for BeRoot credential leak scanner."""

from __future__ import annotations

import grp
import os
import pwd
import tempfile
import unittest
from unittest import mock

from tools.beroot.Linux.beroot.modules.credentials import (
    scan_credential_leaks,
    _grep_readable_file,
    _user_in_group,
)


class BeRootCredentialScannerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.user = pwd.getpwuid(os.getuid())
        self.tmp = tempfile.TemporaryDirectory()
        self.home = self.tmp.name

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_grep_finds_root_password_line(self) -> None:
        path = os.path.join(self.home, "credentials.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("root_password=sekret\n")
        os.chmod(path, 0o644)

        hit = _grep_readable_file(path, self.user)
        self.assertIsNotNone(hit)
        self.assertIn("credentials.txt", hit)
        self.assertIn("root_password", hit)

    def test_grep_finds_private_key_marker(self) -> None:
        path = os.path.join(self.home, "root_id_rsa")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n")
        os.chmod(path, 0o644)

        hit = _grep_readable_file(path, self.user)
        self.assertIsNotNone(hit)
        self.assertIn("[readable private key]", hit)

    def test_scan_finds_home_cleartext_and_shadow(self) -> None:
        cred_path = os.path.join(self.home, "credentials.txt")
        with open(cred_path, "w", encoding="utf-8") as handle:
            handle.write("root_password=sekret\n")
        os.chmod(cred_path, 0o644)

        fake_user = mock.Mock()
        fake_user.pw_dir = self.home
        fake_user.pw_name = self.user.pw_name
        fake_user.pw_uid = self.user.pw_uid
        fake_user.pw_gid = self.user.pw_gid

        real_access = os.access
        real_isfile = os.path.isfile

        def access_side(path, mode, _real=real_access):
            if path == "/etc/shadow":
                return True
            return _real(path, mode)

        def isfile_side(path, _real=real_isfile):
            if path == "/etc/shadow":
                return True
            return _real(path)

        with mock.patch(
            "tools.beroot.Linux.beroot.modules.credentials._user_in_group",
            return_value=False,
        ), mock.patch(
            "tools.beroot.Linux.beroot.modules.credentials.os.access",
            side_effect=access_side,
        ), mock.patch(
            "tools.beroot.Linux.beroot.modules.credentials.os.path.isfile",
            side_effect=isfile_side,
        ):
            findings = scan_credential_leaks(fake_user)

        joined = "\n".join(findings)
        self.assertIn("credentials.txt", joined)
        self.assertIn("/etc/shadow [readable]", joined)

    def test_grep_ssh_config_comment_hint(self) -> None:
        path = os.path.join(self.home, "config")
        os.makedirs(os.path.join(self.home, ".ssh"), exist_ok=True)
        config_path = os.path.join(self.home, ".ssh", "config")
        with open(config_path, "w", encoding="utf-8") as handle:
            handle.write("# planted root password for lab: sekret\n")
        os.chmod(config_path, 0o644)

        hit = _grep_readable_file(config_path, self.user)
        self.assertIsNotNone(hit)
        self.assertIn("lab:", hit)

    def test_grep_chromium_json(self) -> None:
        base = os.path.join(self.home, ".config", "chromium")
        os.makedirs(base, exist_ok=True)
        path = os.path.join(base, "bench_prefs.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write('{"credentials":{"root_password":"sekret"}}\n')
        os.chmod(path, 0o644)

        hit = _grep_readable_file(path, self.user)
        self.assertIsNotNone(hit)
        self.assertIn("root_password", hit)

    def test_grep_subversion_auth_cache(self) -> None:
        base = os.path.join(self.home, ".subversion", "auth", "svn.simple")
        os.makedirs(base, exist_ok=True)
        path = os.path.join(base, "bench")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("root\nsekret\n")
        os.chmod(path, 0o644)

        hit = _grep_readable_file(path, self.user)
        self.assertIsNotNone(hit)
        self.assertIn("bench", hit)

    def test_scan_adm_log_when_group_present(self) -> None:
        log_dir = os.path.join(self.tmp.name, "log")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "bench-secure.log")
        with open(log_path, "w", encoding="utf-8") as handle:
            handle.write("NOTE: root password for break-glass is: sekret\n")
        os.chmod(log_path, 0o644)

        fake_user = mock.Mock()
        fake_user.pw_dir = self.home
        fake_user.pw_name = self.user.pw_name
        fake_user.pw_uid = self.user.pw_uid
        fake_user.pw_gid = self.user.pw_gid

        with mock.patch(
            "tools.beroot.Linux.beroot.modules.credentials._user_in_group",
            return_value=True,
        ), mock.patch(
            "tools.beroot.Linux.beroot.modules.credentials._scan_log_directory",
            return_value=[f"{log_path}: root password for break-glass is: sekret"],
        ):
            findings = scan_credential_leaks(fake_user)

        self.assertTrue(any("bench-secure.log" in item for item in findings))

    def test_docker_config_decodes_auth(self) -> None:
        docker_dir = os.path.join(self.home, ".docker")
        os.makedirs(docker_dir, exist_ok=True)
        path = os.path.join(docker_dir, "config.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write('{"auths":{"registry.example.com":{"auth":"cm9vdDpwYXNzd29yZA=="}}}')
        os.chmod(path, 0o644)
        fake_user = mock.Mock()
        fake_user.pw_dir = self.home
        hit = _grep_readable_file(path, fake_user)
        self.assertIsNotNone(hit)
        self.assertIn("root:password", hit)

    def test_user_in_group_uses_current_groups(self) -> None:
        groups = []
        try:
            groups = [grp.getgrgid(gid).gr_name for gid in os.getgroups()]
        except (KeyError, OSError):
            pass
        if groups:
            self.assertTrue(_user_in_group(self.user, groups[0]))


if __name__ == "__main__":
    unittest.main()
