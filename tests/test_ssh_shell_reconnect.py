"""Tests for SSH shell refresh when create_new=True."""

from __future__ import annotations

import unittest
from unittest import mock

from ramigpt.benchmark.orchestrator import (
    BenchmarkRun,
    TargetRunResult,
    mark_full_ai_finished,
    root_won_by_session,
    full_ai_finished_by_session,
    _current,
)
from ramigpt.benchmark import orchestrator as orch


class OpenSshInteractiveShellTests(unittest.TestCase):
    def test_prefers_login_shell_when_explicit_paths_fail(self):
        from ramigpt.web import app as webapp

        conn = mock.Mock(name="ssh_conn")
        conn.process.return_value = None
        broken = mock.Mock(name="broken_shell")
        login_shell = mock.Mock(name="login_shell")

        def _shell(path=None):
            if path is None:
                return login_shell
            return broken

        conn.system.side_effect = lambda _path: broken
        conn.shell.side_effect = _shell

        shell = webapp._open_ssh_interactive_shell(conn)

        self.assertIs(shell, login_shell)
        conn.shell.assert_called_once_with()
        conn.system.assert_not_called()


class GetOrCreateSshShellTests(unittest.TestCase):
    def test_create_new_closes_stale_shell_before_reconnect(self):
        from ramigpt.web import app as webapp
        from ramigpt.web.shell import connection as conn_mod

        stale_shell = mock.Mock(name="stale_shell")
        webapp.ssh_shells["sid-1"] = stale_shell
        webapp.ssh_ssh_conns["sid-1"] = mock.Mock(name="stale_conn")

        new_shell = mock.Mock(name="new_shell")
        new_conn = mock.Mock(name="new_conn")

        with webapp.app.test_request_context():
            from flask import session as flask_session

            flask_session["username"] = "lowpriv"
            flask_session["password"] = "secret"
            flask_session["server"] = "10.0.0.1"
            flask_session["port"] = 2211

            with mock.patch.object(conn_mod, "close_ssh_connection") as close_mock, mock.patch.object(
                conn_mod, "ssh", return_value=new_conn
            ), mock.patch.object(
                conn_mod, "_open_ssh_interactive_shell", return_value=new_shell
            ), mock.patch.object(conn_mod, "shell_recvuntil"):
                result = webapp.get_or_create_ssh_shell("sid-1", create_new=True)

        close_mock.assert_called_once_with("sid-1")
        self.assertIs(result, new_shell)
        self.assertIs(webapp.ssh_shells["sid-1"], new_shell)
        self.assertIs(webapp.ssh_ssh_conns["sid-1"], new_conn)

    def test_reuses_existing_when_create_new_false(self):
        from ramigpt.web import app as webapp
        from ramigpt.web.shell import connection as conn_mod

        existing = mock.Mock(name="existing_shell")
        webapp.ssh_shells["sid-2"] = existing

        with mock.patch.object(conn_mod, "close_ssh_connection") as close_mock, mock.patch.object(
            conn_mod, "ssh"
        ) as ssh_mock:
            result = webapp.get_or_create_ssh_shell("sid-2", create_new=False)

        close_mock.assert_not_called()
        ssh_mock.assert_not_called()
        self.assertIs(result, existing)

        webapp.ssh_shells.pop("sid-2", None)


class MarkFullAiFinishedMessageTests(unittest.TestCase):
    def setUp(self):
        self._prev_current = orch._current
        root_won_by_session.clear()
        full_ai_finished_by_session.clear()

    def tearDown(self):
        orch._current = self._prev_current
        root_won_by_session.clear()
        full_ai_finished_by_session.clear()

    def test_stop_reason_becomes_target_message(self):
        run = BenchmarkRun(
            id="run-1",
            mode="remote",
            timeout_seconds=180,
            targets=[
                TargetRunResult(
                    target_id="sudo-all",
                    name="Bench · sudo ALL",
                    port=2170,
                    status="running",
                    session_id="sess-a",
                )
            ],
        )
        orch._current = run

        mark_full_ai_finished(
            "sess-a",
            stop_reason="BeRoot failed: Socket is closed",
        )

        self.assertTrue(full_ai_finished_by_session["sess-a"])
        self.assertEqual(run.targets[0].message, "BeRoot failed: Socket is closed")


if __name__ == "__main__":
    unittest.main()
