"""HTTP API for the privilege-escalation benchmark suite."""

from __future__ import annotations

from flask import Flask, jsonify, request

from ramigpt.benchmark.orchestrator import get_status, request_stop, start_run
from ramigpt.benchmark.targets import DEFAULT_TIMEOUT_SECONDS, list_targets
from ramigpt.utils import debug_logger


def register_benchmark_routes(app: Flask) -> None:
    @app.route("/api/benchmark/targets", methods=["GET"])
    def api_benchmark_targets():
        return jsonify(targets=list_targets()), 200

    @app.route("/api/benchmark/status", methods=["GET"])
    def api_benchmark_status():
        return jsonify(get_status()), 200

    @app.route("/api/benchmark/start", methods=["POST"])
    def api_benchmark_start():
        if not request.is_json:
            return jsonify(error="JSON body required"), 400
        body = request.get_json(silent=True) or {}
        mode = (body.get("mode") or "local").strip().lower()
        timeout = body.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
        remote = body.get("remote") or None
        try:
            timeout_i = int(timeout)
        except (TypeError, ValueError):
            return jsonify(error="timeout_seconds must be an integer"), 400
        try:
            run = start_run(mode=mode, timeout_seconds=timeout_i, remote=remote)
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
