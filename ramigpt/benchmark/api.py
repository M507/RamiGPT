"""HTTP API for the privilege-escalation benchmark suite."""

from __future__ import annotations

from flask import Flask, jsonify, request

from ramigpt.benchmark.deploy import RemoteDeployConfig, test_ssh_access
from ramigpt.benchmark.orchestrator import get_status, request_stop, start_run
from ramigpt.benchmark.remote_config import load_remote_config, merge_remote_override, public_remote_config
from ramigpt.benchmark.targets import DEFAULT_TIMEOUT_SECONDS, list_targets
from ramigpt.utils import debug_logger


def register_benchmark_routes(app: Flask) -> None:
    @app.route("/api/benchmark/targets", methods=["GET"])
    def api_benchmark_targets():
        return jsonify(targets=list_targets()), 200

    @app.route("/api/benchmark/status", methods=["GET"])
    def api_benchmark_status():
        return jsonify(get_status()), 200

    @app.route("/api/benchmark/remote-config", methods=["GET"])
    def api_benchmark_remote_config():
        return jsonify(public_remote_config()), 200

    @app.route("/api/benchmark/remote/test", methods=["POST"])
    def api_benchmark_remote_test():
        body = request.get_json(silent=True) or {}
        merged = merge_remote_override(
            body.get("remote") if isinstance(body.get("remote"), dict) else body
        )
        if not merged.get("host") or not merged.get("username") or not merged.get("password"):
            return jsonify(
                ok=False,
                error="host, username, and password required (from UI or data/benchmark/remote.json)",
            ), 400
        try:
            result = test_ssh_access(
                RemoteDeployConfig(
                    host=merged["host"],
                    username=merged["username"],
                    password=merged["password"],
                    port=int(merged.get("port") or 22),
                )
            )
            return jsonify(result), 200
        except Exception as exc:  # noqa: BLE001
            debug_logger.exception("Remote SSH test failed")
            return jsonify(ok=False, error=str(exc)), 400

    @app.route("/api/benchmark/start", methods=["POST"])
    def api_benchmark_start():
        if not request.is_json:
            return jsonify(error="JSON body required"), 400
        body = request.get_json(silent=True) or {}
        preset = load_remote_config()
        mode = (body.get("mode") or preset.get("mode") or "local").strip().lower()
        timeout = body.get("timeout_seconds", preset.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
        remote = body.get("remote") or None
        tools = body.get("tools", preset.get("tools"))
        try:
            timeout_i = int(timeout)
        except (TypeError, ValueError):
            return jsonify(error="timeout_seconds must be an integer"), 400
        try:
            run = start_run(mode=mode, timeout_seconds=timeout_i, remote=remote, tools=tools)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except RuntimeError as exc:
            return jsonify(error=str(exc)), 409
        except Exception as exc:  # noqa: BLE001
            debug_logger.exception("Failed to start benchmark")
            return jsonify(error=str(exc)), 500
        return jsonify(ok=True, run=run.to_public_dict()), 202

    @app.route("/api/benchmark/stop", methods=["POST"])
    def api_benchmark_stop():
        result = request_stop()
        code = 200 if result.get("ok") else 409
        return jsonify(result), code
