#!/usr/bin/env python3
"""Verify /action3 routes linenum and execute_linenum is registered for benchmarks."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("PWNLIB_NOTERM", "1")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class Action3LinEnumRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import ramigpt.web.app as app_module

        cls.app_module = app_module
        cls.app = app_module.app
        cls.client = cls.app.test_client()

    def test_tool_executors_include_linenum(self):
        self.assertIn("linenum", self.app_module._TOOL_EXECUTORS)
        self.assertIs(
            self.app_module._TOOL_EXECUTORS["linenum"],
            self.app_module.execute_linenum,
        )
        self.assertIn("linpeas", self.app_module._TOOL_EXECUTORS)
        self.assertIs(
            self.app_module._TOOL_EXECUTORS["linpeas"],
            self.app_module.execute_linpeas,
        )

    def test_action3_start_linenum(self):
        mock_socketio = MagicMock()
        app_mod = self.app_module
        from ramigpt.web import state as web_state
        from ramigpt.web.routes import ssh as ssh_routes

        with patch.object(ssh_routes, "socketio", mock_socketio), patch.object(
            ssh_routes, "resolve_server_session_id", return_value="sess-linenum-test"
        ), patch.object(web_state, "ssh_shells", {"sess-linenum-test": MagicMock()}), patch.object(
            web_state, "ssh_ssh_conns", {"sess-linenum-test": MagicMock()}
        ), patch.object(ssh_routes, "emit_session"), patch.object(web_state, "loop", {}):
            with self.client.session_transaction() as sess:
                sess["username"] = "lowpriv"
                sess["password"] = "password"
            resp = self.client.post(
                "/action3",
                json={"action": "start", "ai": False, "tool": "linenum"},
            )
        self.assertEqual(resp.status_code, 200, resp.get_json())
        body = resp.get_json()
        self.assertEqual(body.get("tool"), "linenum")
        self.assertEqual(body.get("output"), "linenum_started")
        mock_socketio.start_background_task.assert_called_once()
        args = mock_socketio.start_background_task.call_args[0]
        self.assertIs(args[0], app_mod.execute_linenum)

    def test_action3_start_linpeas(self):
        mock_socketio = MagicMock()
        app_mod = self.app_module
        from ramigpt.web import state as web_state
        from ramigpt.web.routes import ssh as ssh_routes

        with patch.object(ssh_routes, "socketio", mock_socketio), patch.object(
            ssh_routes, "resolve_server_session_id", return_value="sess-linpeas-test"
        ), patch.object(web_state, "ssh_shells", {"sess-linpeas-test": MagicMock()}), patch.object(
            web_state, "ssh_ssh_conns", {"sess-linpeas-test": MagicMock()}
        ), patch.object(ssh_routes, "emit_session"), patch.object(web_state, "loop", {}):
            with self.client.session_transaction() as sess:
                sess["username"] = "lowpriv"
                sess["password"] = "password"
            resp = self.client.post(
                "/action3",
                json={"action": "start", "ai": False, "tool": "linpeas"},
            )
        self.assertEqual(resp.status_code, 200, resp.get_json())
        body = resp.get_json()
        self.assertEqual(body.get("tool"), "linpeas")
        mock_socketio.start_background_task.assert_called_once()
        args = mock_socketio.start_background_task.call_args[0]
        self.assertIs(args[0], app_mod.execute_linpeas)


class BenchmarkHookTest(unittest.TestCase):
    def test_execute_linenum_hook_registered(self):
        import ramigpt.web.app  # noqa: F401 — registers hooks on import
        from ramigpt.benchmark import orchestrator

        self.assertIsNotNone(orchestrator._hooks.get("execute_linenum"))
        self.assertIsNotNone(orchestrator._hooks.get("execute_linpeas"))

    def test_pick_linenum_for_benchmark(self):
        from ramigpt.benchmark.tools import pick_benchmark_tool

        self.assertEqual(
            pick_benchmark_tool({"beroot": False, "linenum": True}),
            "linenum",
        )


if __name__ == "__main__":
    unittest.main()
