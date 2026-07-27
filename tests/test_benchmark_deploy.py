"""Tests for benchmark deploy fast-path logic."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from ramigpt.benchmark.deploy import (
    RemoteDeployConfig,
    check_target_ports,
    ensure_remote_benchmark,
    verify_targets_ssh,
    _ansible_failure_summary,
    _command_failure_message,
)
from ramigpt.benchmark.targets import TARGETS


class BenchmarkDeployFastPathTests(unittest.TestCase):
    def setUp(self):
        self.cfg = RemoteDeployConfig(
            host="10.10.1.109",
            username="root",
            password="secret",
            port=22,
        )
        self.targets = [t for t in TARGETS if t.id in {"sudo-vim", "sudo-awk"}]

    @patch("ramigpt.benchmark.deploy.deploy_remote")
    @patch("ramigpt.benchmark.deploy.verify_targets_ssh")
    @patch("ramigpt.benchmark.deploy.check_target_ports")
    def test_skips_ansible_when_ports_open_and_ssh_ok(
        self, mock_ports, mock_verify, mock_deploy
    ):
        mock_ports.return_value = [
            {"id": t.id, "host": self.cfg.host, "port": t.port, "open": True}
            for t in self.targets
        ]
        mock_verify.return_value = (True, [])

        host = ensure_remote_benchmark(self.cfg, log=lambda _m: None, targets=self.targets)

        self.assertEqual(host, self.cfg.host)
        mock_deploy.assert_not_called()
        mock_verify.assert_called_once()

    @patch("ramigpt.benchmark.deploy.deploy_remote")
    @patch("ramigpt.benchmark.deploy.verify_targets_ssh")
    @patch("ramigpt.benchmark.deploy.check_target_ports")
    def test_runs_ansible_when_port_closed(self, mock_ports, mock_verify, mock_deploy):
        mock_ports.return_value = [
            {"id": self.targets[0].id, "host": self.cfg.host, "port": self.targets[0].port, "open": True},
            {"id": self.targets[1].id, "host": self.cfg.host, "port": self.targets[1].port, "open": False},
        ]
        mock_deploy.return_value = self.cfg.host

        host = ensure_remote_benchmark(self.cfg, log=lambda _m: None, targets=self.targets)

        self.assertEqual(host, self.cfg.host)
        mock_deploy.assert_called_once()
        mock_verify.assert_not_called()

    @patch("ramigpt.benchmark.deploy.deploy_remote")
    @patch("ramigpt.benchmark.deploy.verify_targets_ssh")
    @patch("ramigpt.benchmark.deploy.check_target_ports")
    def test_runs_ansible_when_ssh_verify_fails(self, mock_ports, mock_verify, mock_deploy):
        mock_ports.return_value = [
            {"id": t.id, "host": self.cfg.host, "port": t.port, "open": True}
            for t in self.targets
        ]
        mock_verify.return_value = (False, [self.targets[0].id])
        mock_deploy.return_value = self.cfg.host

        ensure_remote_benchmark(self.cfg, log=lambda _m: None, targets=self.targets)

        mock_deploy.assert_called_once()

    @patch("ramigpt.benchmark.deploy.deploy_remote")
    @patch("ramigpt.benchmark.deploy.check_target_ports")
    def test_force_deploy_skips_fast_path(self, mock_ports, mock_deploy):
        mock_deploy.return_value = self.cfg.host

        ensure_remote_benchmark(
            self.cfg, log=lambda _m: None, targets=self.targets, force_deploy=True
        )

        mock_ports.assert_not_called()
        mock_deploy.assert_called_once()

    @patch("ramigpt.benchmark.deploy._tcp_port_open")
    def test_check_target_ports_parallel_order(self, mock_tcp):
        mock_tcp.return_value = True
        results = check_target_ports(
            "127.0.0.1", log=lambda _m: None, targets=self.targets, parallel=True
        )
        self.assertEqual([r["id"] for r in results], [t.id for t in self.targets])
        self.assertTrue(all(r["open"] for r in results))

    @patch("ramigpt.benchmark.deploy._probe_target_ssh")
    def test_verify_targets_ssh_collects_failures(self, mock_probe):
        mock_probe.side_effect = [True, False]
        ok, failed = verify_targets_ssh(
            "127.0.0.1", self.targets, log=lambda _m: None, parallel=False
        )
        self.assertFalse(ok)
        self.assertEqual(failed, [self.targets[1].id])

    def test_ansible_paramiko_failure_message_for_ui(self):
        play_out = "\n".join(
            [
                "PLAY [Deploy RamiGPT privilege-escalation benchmark targets] *******************",
                "",
                "TASK [Gathering Facts] *********************************************************",
                "[ERROR]: Task failed: the connection plugin 'paramiko' was not found",
                'fatal: [bench]: FAILED! => {"changed": false, "msg": "Task failed: the connection plugin \'paramiko\' was not found"}',
                "",
                "PLAY RECAP *********************************************************************",
                "bench                      : ok=0    changed=0    unreachable=0    failed=1    skipped=0    rescued=0    ignored=0",
            ]
        )
        summary = _ansible_failure_summary(play_out)
        self.assertIn("paramiko", summary)
        self.assertIn("connection plugin", summary.lower())

        msg = _command_failure_message(
            2,
            ["/root/RamiGPT/venv/bin/ansible-playbook", "-i", "/tmp/inv.ini", "playbook.yml"],
            play_out,
            "",
        )
        self.assertIn("Ansible deploy failed:", msg)
        self.assertIn("paramiko", msg)
        self.assertIn("Command failed (2):", msg)
        self.assertIn("PLAY [Deploy RamiGPT", msg)
        self.assertIn("Gathering Facts", msg)
        # Headline + full play output both present and separated.
        self.assertIn("\n\n", msg)

    def test_ansible_python38_target_failure_message_for_ui(self):
        from ramigpt.benchmark.deploy import _ansible_failure_hint

        play_out = (
            "TASK [Gathering Facts] *********************************************************\n"
            "Ansible requires Python 3.9 or newer on the target. Current version: 3.8.10 "
            "(default, Mar 18 2025, 20:04:55) [GCC 9.4.0]\n"
            'fatal: [bench]: FAILED! => {"msg": "The following modules failed to execute: ansible.legacy.setup."}'
        )
        summary = _ansible_failure_summary(play_out)
        self.assertIn("Python 3.9", summary)
        hint = _ansible_failure_hint(play_out)
        self.assertIn("3.8", hint)
        msg = _command_failure_message(
            2,
            ["ansible-playbook", "playbook.yml"],
            play_out,
            "",
        )
        self.assertIn("Ansible deploy failed:", msg)
        self.assertIn("Hint:", msg)
        self.assertIn("Command failed (2):", msg)

    def test_command_failure_keeps_both_stdout_and_stderr(self):
        msg = _command_failure_message(
            1,
            ["ansible-playbook", "x.yml"],
            "PLAY [x]\nfatal: [bench]: FAILED! => {\"msg\": \"boom\"}",
            "warning: something",
        )
        self.assertIn("boom", msg)
        self.assertIn("warning: something", msg)


if __name__ == "__main__":
    unittest.main()
