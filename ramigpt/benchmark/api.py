"""HTTP API for the privilege-escalation benchmark suite."""

from __future__ import annotations

from flask import Flask, jsonify, request

from ramigpt.benchmark.deploy import RemoteDeployConfig, test_ssh_access
from ramigpt.benchmark.orchestrator import get_status, request_stop, start_run
from ramigpt.benchmark.remote_config import load_remote_config, merge_remote_override, public_remote_config
from ramigpt.ai.model_catalog import list_models_for_provider, saved_model_for_provider
from ramigpt.benchmark.targets import (
    BENCH_PASSWORD,
    BENCH_USERNAME,
    DEFAULT_TIMEOUT_SECONDS,
    list_profiles,
    list_targets,
)
from ramigpt.benchmark.verify import get_verify_status, request_stop_verify, start_verify_async
from ramigpt.config import get_settings
from ramigpt.utils import debug_logger
from ramigpt.utils.session_logging import clear_all_session_logs


def register_benchmark_routes(app: Flask) -> None:
    @app.route("/api/benchmark/targets", methods=["GET"])
    def api_benchmark_targets():
        return jsonify(targets=list_targets(), profiles=list_profiles()), 200

    @app.route("/api/benchmark/status", methods=["GET"])
    def api_benchmark_status():
        return jsonify(get_status()), 200

    @app.route("/api/benchmark/models", methods=["POST"])
    def api_benchmark_models():
        """List models for a provider using saved AI settings credentials."""
        body = request.get_json(silent=True) or {}
        provider = (body.get("provider") or "").strip().lower()
        if not provider:
            return jsonify(success=False, error="provider is required", models=[], count=0), 400
        try:
            models = list_models_for_provider(provider)
            cfg = get_settings()
            return jsonify(
                success=True,
                provider=provider,
                models=models,
                count=len(models),
                saved_model=saved_model_for_provider(cfg, provider),
            ), 200
        except ValueError as exc:
            return jsonify(success=False, error=str(exc), models=[], count=0), 400
        except Exception as exc:  # noqa: BLE001
            debug_logger.warning(f"benchmark.list_models failed provider={provider}: {exc}")
            return jsonify(success=False, error=str(exc), models=[], count=0), 400

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

    @app.route("/api/benchmark/verify", methods=["POST"])
    def api_benchmark_verify_start():
        """Run per-target root probes against already-deployed containers on the remote lab."""
        body = request.get_json(silent=True) or {}
        preset = load_remote_config()
        host = (
            (body.get("host") or "").strip()
            or (
                (body.get("remote") or {}).get("host")
                if isinstance(body.get("remote"), dict)
                else ""
            )
            or preset.get("host")
            or ""
        )
        if not host:
            return jsonify(
                ok=False,
                error="host is required (remote lab IP with benchmark SSH ports)",
            ), 400
        target_ids = body.get("target_ids", body.get("targets"))
        if isinstance(target_ids, list) and len(target_ids) == 0:
            return jsonify(ok=False, error="Select at least one benchmark target"), 400
        user = (body.get("username") or BENCH_USERNAME).strip() or BENCH_USERNAME
        password = body.get("password") if body.get("password") is not None else BENCH_PASSWORD
        if password == "":
            password = BENCH_PASSWORD
        try:
            run = start_verify_async(
                host,
                target_ids=target_ids if isinstance(target_ids, list) else None,
                user=user,
                password=str(password),
            )
        except ValueError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        except RuntimeError as exc:
            return jsonify(ok=False, error=str(exc)), 409
        except Exception as exc:  # noqa: BLE001
            debug_logger.exception("Failed to start misconfig verify")
            return jsonify(ok=False, error=str(exc)), 500
        return jsonify(ok=True, run=run), 202

    @app.route("/api/benchmark/verify/status", methods=["GET"])
    def api_benchmark_verify_status():
        return jsonify(get_verify_status()), 200

    @app.route("/api/benchmark/verify/stop", methods=["POST"])
    def api_benchmark_verify_stop():
        return jsonify(request_stop_verify()), 200

    @app.route("/api/benchmark/start", methods=["POST"])
    def api_benchmark_start():
        if not request.is_json:
            return jsonify(error="JSON body required"), 400
        body = request.get_json(silent=True) or {}
        preset = load_remote_config()
        mode = "remote"
        timeout = body.get("timeout_seconds", preset.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
        remote = body.get("remote") or None
        tools = body.get("tools", preset.get("tools"))
        repetitions = body.get("repetitions", body.get("runs", body.get("run_times", 1)))
        run_plan = body.get("run_plan")
        role_plan = body.get("role_plan")
        role_repetitions = body.get(
            "role_repetitions",
            body.get("role_runs", body.get("role_run_times", 1)),
        )
        target_ids = body.get("target_ids", body.get("targets"))
        try:
            timeout_i = int(timeout)
        except (TypeError, ValueError):
            return jsonify(error="timeout_seconds must be an integer"), 400
        try:
            run = start_run(
                mode=mode,
                timeout_seconds=timeout_i,
                remote=remote,
                tools=tools,
                repetitions=repetitions,
                run_plan=run_plan if isinstance(run_plan, list) else None,
                role_plan=role_plan if isinstance(role_plan, list) else None,
                role_repetitions=role_repetitions,
                target_ids=target_ids,
            )
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

    @app.route("/api/benchmark/clean-logs", methods=["POST"])
    def api_benchmark_clean_logs():
        status = get_status()
        if status.get("running"):
            return jsonify(
                ok=False,
                error="Stop the active benchmark before cleaning logs",
            ), 409
        try:
            result = clear_all_session_logs()
            return jsonify(ok=True, **result), 200
        except Exception as exc:  # noqa: BLE001
            debug_logger.exception("Failed to clean session logs")
            return jsonify(ok=False, error=str(exc)), 500
