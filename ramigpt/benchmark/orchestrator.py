"""Orchestrate deploy → SSH sessions → Full AI → pass/fail with timeout."""

from __future__ import annotations

import json
import threading
import time
import uuid
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from flask import Flask

from ramigpt.benchmark.deploy import (
    RemoteDeployConfig,
    ensure_remote_benchmark,
)
from ramigpt.benchmark.remote_config import load_remote_config, merge_remote_override, public_remote_config
from ramigpt.benchmark.targets import (
    BENCH_GROUP_ID,
    BENCH_PASSWORD,
    BENCH_USERNAME,
    DEFAULT_TIMEOUT_SECONDS,
    TARGETS,
    BenchmarkTarget,
    list_profiles,
    resolve_targets,
)
from ramigpt.benchmark.results import (
    build_result_document,
    enrich_target_from_events,
    write_batch_summary,
    write_benchmark_result,
)
from ramigpt.benchmark.run_plan import (
    apply_plan_entry_model,
    describe_run_plan,
    flatten_run_plan,
    normalize_run_plan,
)
from ramigpt.benchmark.tools import AVAILABLE_TOOLS, default_tools, enabled_tool_ids, normalize_tools
from ramigpt.config import Settings, get_settings, get_settings_manager
from ramigpt.domain import PrivEscPrompt
from ramigpt.paths import BENCHMARK_RESULTS_DIR
from ramigpt.services.runtime_status import set_status
from ramigpt.services.session_store import get_session_store
from ramigpt.utils import debug_logger
from ramigpt.utils.session_logging import (
    append_benchmark_suite_log,
    begin_benchmark_suite_logs,
    begin_benchmark_target_logs,
    reset_session_log_dir,
    write_benchmark_suite_snapshot,
)

# Filled by web layer so the orchestrator can reuse live SSH / Full AI primitives.
_hooks: Dict[str, Any] = {}


def register_benchmark_hooks(**kwargs: Any) -> None:
    """Inject runtime dependencies from ramigpt.web.app (SSH shells, autonomous, …)."""
    global root_won_by_session, full_ai_finished_by_session
    _hooks.update(kwargs)
    # Share the app-level flag maps so Full AI root detection and the
    # benchmark waiter always read/write the same objects.
    shared_root = kwargs.get("root_won_by_session")
    if isinstance(shared_root, dict):
        root_won_by_session = shared_root
    shared_done = kwargs.get("full_ai_finished_by_session")
    if isinstance(shared_done, dict):
        full_ai_finished_by_session = shared_done


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TargetRunResult:
    target_id: str
    name: str
    port: int
    status: str = "pending"  # pending|deploying|running|passed|failed|error|skipped
    session_id: Optional[str] = None
    elapsed_seconds: Optional[float] = None
    message: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    ai_requests: Optional[int] = None
    tools_used: List[str] = field(default_factory=list)
    provider: str = ""
    model: str = ""
    got_root: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BenchmarkRun:
    id: str
    mode: str  # remote (Ansible deploy to lab host)
    timeout_seconds: int
    phase: str = "queued"  # queued|deploying|running|stopping|done|error
    host: str = ""
    remote: Optional[Dict[str, Any]] = None
    # tool_id -> enabled (BeRoot default on). Enabled tools run before Full AI with AI on.
    tools: Dict[str, bool] = field(default_factory=default_tools)
    targets: List[TargetRunResult] = field(default_factory=list)
    log: List[str] = field(default_factory=list)
    started_at: str = field(default_factory=_utcnow)
    finished_at: Optional[str] = None
    error: Optional[str] = None
    stop_requested: bool = False
    # On-disk suite folder: data/logs/sessions/benchmarks/<id>/
    log_dir: Optional[str] = None
    # Multi-run batch metadata (repetition of N)
    batch_id: Optional[str] = None
    repetition: int = 1
    repetitions: int = 1
    provider: str = ""
    model: str = ""
    result_dir: Optional[str] = None

    def to_public_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        # Never return remote password to the UI.
        if data.get("remote") and "password" in data["remote"]:
            remote = dict(data["remote"])
            remote["password"] = "***" if remote.get("password") else ""
            remote["password_set"] = bool(self.remote and self.remote.get("password"))
            data["remote"] = remote
        return data


_lock = threading.RLock()
_current: Optional[BenchmarkRun] = None
_history: List[Dict[str, Any]] = []
# session_id -> True when Full AI / autonomous detects root
root_won_by_session: Dict[str, bool] = {}
full_ai_finished_by_session: Dict[str, bool] = {}
# Multi-run batch state (active until all repetitions finish)
_batch: Dict[str, Any] = {
    "active": False,
    "id": None,
    "repetition": 0,
    "repetitions": 1,
    "run_plan": None,
    "current_provider": "",
    "current_model": "",
    "stop": False,
}


def mark_root_won(session_id: str) -> None:
    root_won_by_session[session_id] = True
    with _lock:
        run = _current
        if not run:
            return
        for item in run.targets:
            if item.session_id == session_id:
                item.got_root = True
                break


def mark_full_ai_finished(
    session_id: str,
    *,
    requests_run: Optional[int] = None,
    got_root: Optional[bool] = None,
    provider: str = "",
    model: str = "",
    stop_reason: str = "",
) -> None:
    full_ai_finished_by_session[session_id] = True
    with _lock:
        run = _current
        if not run:
            return
        if provider:
            run.provider = provider
        if model:
            run.model = model
        for item in run.targets:
            if item.session_id != session_id:
                continue
            if requests_run is not None:
                try:
                    item.ai_requests = int(requests_run)
                except (TypeError, ValueError):
                    pass
            if got_root is not None:
                item.got_root = bool(got_root)
            if provider:
                item.provider = provider
            if model:
                item.model = model
            if stop_reason and not item.message and item.status == "running":
                item.message = stop_reason
            break


def get_current_run() -> Optional[BenchmarkRun]:
    with _lock:
        return _current


def get_status() -> Dict[str, Any]:
    with _lock:
        run = _current
        remote_cfg = public_remote_config()
        batch_active = bool(_batch.get("active"))
        running = batch_active or bool(run and run.phase not in {"done", "error"})
        run_dict = run.to_public_dict() if run else None
        if run_dict and run_dict.get("log_dir"):
            suite_dir = run_dict["log_dir"]
            tools_cfg = run_dict.get("tools") or {}
            run_dict["targets"] = [
                enrich_target_from_events(dict(t), suite_dir, tools_configured=tools_cfg)
                for t in run_dict.get("targets") or []
            ]
            issues = []
            for t in run_dict["targets"]:
                issues.extend(t.get("issues") or [])
            if issues:
                run_dict["issues"] = issues
        return {
            "running": running,
            "run": run_dict,
            "batch": {
                "active": batch_active,
                "id": _batch.get("id"),
                "repetition": _batch.get("repetition"),
                "repetitions": _batch.get("repetitions"),
                "run_plan": _batch.get("run_plan"),
                "current_provider": _batch.get("current_provider"),
                "current_model": _batch.get("current_model"),
            },
            "targets": [t.to_dict() for t in TARGETS],
            "profiles": list_profiles(),
            "defaults": {
                "timeout_seconds": int(
                    remote_cfg.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS
                ),
                "repetitions": 1,
                "username": BENCH_USERNAME,
                "password": BENCH_PASSWORD,
                "ports": [t.port for t in TARGETS],
                "target_ids": [t.id for t in TARGETS],
                "tools": remote_cfg.get("tools") or default_tools(),
            },
            "ai_settings": {
                "provider": get_settings().ai_provider,
                "model": get_settings().active_model(),
                "saved_models": {
                    "ollama": get_settings().ollama_model,
                    "openai": get_settings().openai_model,
                    "openwebui": get_settings().openwebui_model,
                    "cursor": get_settings().cursor_model,
                },
            },
            "available_tools": AVAILABLE_TOOLS,
            "remote_preset": remote_cfg,
            "history": list(_history[-10:]),
        }


def request_stop() -> Dict[str, Any]:
    with _lock:
        _batch["stop"] = True
        if not _current or _current.phase in {"done", "error"}:
            if _batch.get("active"):
                return {"ok": True, "run": _current.to_public_dict() if _current else None}
            return {"ok": False, "error": "No active benchmark run"}
        _current.stop_requested = True
        _current.phase = "stopping"
        _current.log.append(f"[{_utcnow()}] Stop requested")
        stop_flags = _hooks.get("stop_full_ai_by_session") or {}
        for item in _current.targets:
            if item.session_id and item.session_id in stop_flags:
                stop_flags[item.session_id].set()
        return {"ok": True, "run": _current.to_public_dict()}


def _reload_ai_settings() -> Settings:
    """Reload AI Settings from disk so benchmarks use the latest saved provider/model."""
    return get_settings_manager().reload()


def _sync_run_ai_settings(run: BenchmarkRun, settings: Optional[Settings] = None) -> Settings:
    """Copy the active AI provider/model onto the run record."""
    cfg = settings or _reload_ai_settings()
    run.provider = cfg.ai_provider
    run.model = cfg.active_model()
    return cfg


def _log(run: BenchmarkRun, message: str) -> None:
    line = f"[{_utcnow()}] {message}"
    run.log.append(line)
    debug_logger.info(f"[benchmark] {message}")
    if run.log_dir:
        append_benchmark_suite_log(Path(run.log_dir), line)
    emit = _hooks.get("emit_benchmark")
    if callable(emit):
        try:
            emit(message)
        except Exception:  # noqa: BLE001
            pass


def _ensure_benchmark_group() -> None:
    store = get_session_store()
    store.ensure_group(BENCH_GROUP_ID, "Benchmark", order=99)

def _upsert_session_for_target(target: BenchmarkTarget, host: str) -> str:
    store = get_session_store()
    _ensure_benchmark_group()
    snap = store.snapshot()
    existing = None
    for sess in snap.get("sessions", []):
        if (
            sess.get("host") == host
            and int(sess.get("port") or 0) == target.port
            and sess.get("username") == BENCH_USERNAME
            and sess.get("group_id") == BENCH_GROUP_ID
        ):
            existing = sess
            break

    payload = {
        "name": target.name,
        "host": host,
        "port": target.port,
        "username": BENCH_USERNAME,
        "password": BENCH_PASSWORD,
        "hostname": target.hostname,
        "group_id": BENCH_GROUP_ID,
        "environment": "benchmark",
        "favorite": False,
        "remember_credentials": True,
        "notes": "",
        "facts": [],
        "hints": [],
        "avoids": [],
    }
    if existing:
        updated = store.update_session(existing["id"], payload)
        store.set_prompt_context(
            updated.id,
            facts=payload["facts"],
            hints=payload["hints"],
            avoids=payload["avoids"],
        )
        return updated.id
    created = store.create_session(payload)
    return created.id


def _connect_session(session_id: str) -> None:
    open_ssh = _hooks["open_ssh_connection"]
    start_listener = _hooks["start_shell_listener"]
    prompts = _hooks["prompts"]
    prompt_delimiters = _hooks["prompt_delimiters"]
    emit_session = _hooks["emit_session"]
    flask_app: Flask = _hooks["flask_app"]

    store = get_session_store()
    saved = store.get_session(session_id)
    if not saved:
        raise RuntimeError(f"Session {session_id} missing")

    with flask_app.test_request_context():
        from flask import session as flask_session

        flask_session["logged_in"] = True
        flask_session["username"] = saved.username
        flask_session["password"] = store.resolve_password(saved) or BENCH_PASSWORD
        flask_session["server"] = saved.host
        flask_session["port"] = saved.port
        flask_session["hostname"] = saved.hostname or saved.name
        flask_session["active_server_session_id"] = session_id

        set_status(session_id, "connecting")
        shell = open_ssh(session_id, create_new=True)
        if shell is None:
            set_status(session_id, "error", "SSH connect failed")
            raise RuntimeError(f"Failed to SSH to {saved.host}:{saved.port}")

        # Privilege-escalation goal is root; hostname is only for logging/root detection.
        priv = PrivEscPrompt(
            saved.username,
            flask_session["password"],
            f"{saved.username}@{saved.host}",
            "root",
        )
        for fact in saved.facts:
            priv.add_facts(fact)
        for hint in saved.hints:
            priv.add_hint(hint)
        for avoid in saved.avoids:
            priv.add_avoid(avoid)
        seed = _hooks.get("seed_prompt_history")
        if callable(seed):
            try:
                seed(session_id, priv)
            except Exception as exc:  # noqa: BLE001
                debug_logger.warning(f"benchmark history seed: {exc}")
        else:
            try:
                from ramigpt.utils.session_logging import load_shell_command_history
                priv.merge_history_entries(load_shell_command_history(session_id))
            except Exception:  # noqa: BLE001
                pass
        prompts[session_id] = priv
        prompt_delimiters[session_id] = b"$ "
        store.touch_recent(session_id)
        set_status(session_id, "connected")
        start_listener(session_id)
        emit_session(session_id, f"[benchmark] Connected {saved.host}:{saved.port}", color="#58a6ff")


def _disconnect_session(session_id: str) -> None:
    close_ssh = _hooks.get("close_ssh_connection")
    if callable(close_ssh):
        try:
            close_ssh(session_id)
        except Exception as exc:  # noqa: BLE001
            debug_logger.warning(f"benchmark disconnect: {exc}")
    set_status(session_id, "disconnected")


def _start_full_ai(session_id: str) -> None:
    store = get_session_store()
    saved = store.get_session(session_id)
    stop_flags = _hooks["stop_full_ai_by_session"]
    loop = _hooks["loop"]

    root_won_by_session[session_id] = False
    full_ai_finished_by_session[session_id] = False
    flag = stop_flags.setdefault(session_id, threading.Event())
    flag.clear()
    loop[session_id] = 1

    session_data = {
        "sid": session_id,
        "username": saved.username if saved else BENCH_USERNAME,
        "password": (store.resolve_password(saved) if saved else None) or BENCH_PASSWORD,
        "hostname": saved.hostname if saved else "pehost",
        "server": saved.host if saved else "127.0.0.1",
        "port": saved.port if saved else 22,
        "from_benchmark": True,
        "use_os_thread": True,
    }

    starter = _hooks.get("start_autonomous_task")
    if callable(starter):
        starter(session_data)
        debug_logger.info(
            f"[benchmark] Full AI spawned via start_autonomous_task session_id={session_id}"
        )
        return

    # Fallback — same OS-thread semantics as start_autonomous_task.
    flask_app: Flask = _hooks["flask_app"]
    autonomous = _hooks["autonomous"]

    def _runner() -> None:
        with flask_app.app_context():
            try:
                autonomous(session_data)
            finally:
                mark_full_ai_finished(session_id)

    threading.Thread(
        target=_runner, name=f"bench-ai-{session_id[:8]}", daemon=True
    ).start()


def _session_data(session_id: str) -> Dict[str, Any]:
    store = get_session_store()
    saved = store.get_session(session_id)
    return {
        "sid": session_id,
        "username": saved.username if saved else BENCH_USERNAME,
        "password": (store.resolve_password(saved) if saved else None) or BENCH_PASSWORD,
        "hostname": saved.hostname if saved else "pehost",
        "server": saved.host if saved else "127.0.0.1",
        "port": saved.port if saved else 22,
    }


def _start_tools_then_full_ai(run: BenchmarkRun, session_id: str) -> None:
    """
    Run enabled tools first (BeRoot with AI on → Full AI loop), or plain Full AI
    when no tools are selected.
    """
    enabled = enabled_tool_ids(run.tools)
    root_won_by_session[session_id] = False
    full_ai_finished_by_session[session_id] = False
    stop_flags = _hooks["stop_full_ai_by_session"]
    flag = stop_flags.setdefault(session_id, threading.Event())
    flag.clear()
    loop = _hooks["loop"]
    loop[session_id] = 1

    session_data = _session_data(session_id)

    if "beroot" in enabled:
        execute_beroot = _hooks.get("execute_beroot")
        if not callable(execute_beroot):
            raise RuntimeError("execute_beroot hook not registered")
        _log(run, "Running BeRoot (AI on) — scan then Full AI until root")
        session_data["with_ai"] = True
        # Run Full AI on an OS thread (time.sleep). start_background_task from
        # this benchmark worker never executes under eventlet.
        session_data["from_benchmark"] = True
        session_data["use_os_thread"] = True
        # Record tool usage on the matching target.
        with _lock:
            for item in run.targets:
                if item.session_id == session_id and "beroot" not in item.tools_used:
                    item.tools_used.append("beroot")
        try:
            execute_beroot(session_data)
        except Exception as exc:  # noqa: BLE001
            mark_full_ai_finished(session_id, stop_reason=f"BeRoot failed: {exc}")
            raise
        # If BeRoot path did not hand off to Full AI, avoid hanging the wait loop.
        if not full_ai_finished_by_session.get(session_id) and loop.get(session_id) == 0:
            # Scan-only / failed handoff — mark finished so the target exits cleanly.
            if not root_won_by_session.get(session_id):
                mark_full_ai_finished(session_id)
        return

    if enabled:
        unknown = ", ".join(enabled)
        _log(run, f"Unknown tools {unknown!r} — falling back to Full AI only")

    _log(run, "Starting Full AI (no pre-tools)")
    _start_full_ai(session_id)


def _stop_full_ai(session_id: str) -> None:
    stop_flags = _hooks["stop_full_ai_by_session"]
    flag = stop_flags.setdefault(session_id, threading.Event())
    flag.set()
    # Leave loop[session_id]=1 until autonomous finally clears it so the
    # interactive listener cannot steal the prompt mid-drain.


def _run_target(run: BenchmarkRun, item: TargetRunResult, target: BenchmarkTarget) -> None:
    item.status = "running"
    item.started_at = _utcnow()
    started = time.monotonic()
    _log(run, f"Target {target.name} ({run.host}:{target.port}) — connecting")

    session_id: Optional[str] = None
    try:
        session_id = _upsert_session_for_target(target, run.host)
        item.session_id = session_id

        if run.log_dir:
            slog = begin_benchmark_target_logs(
                suite_dir=Path(run.log_dir),
                run_id=run.id,
                target_id=target.id,
                target_name=target.name,
                session_id=session_id,
                host=run.host,
                port=target.port,
            )
            events = str(slog.events_path) if slog.events_path else ""
            session_log = (
                str(slog.run_dir / "session.log") if slog.run_dir else ""
            )
            debug_logger.info(
                f"[benchmark] target={target.id} session_id={session_id} "
                f"session details → events={events} session_log={session_log}"
            )
            _log(
                run,
                f"Target {target.name} session details → {events}",
            )

        _connect_session(session_id)
        ai_cfg = _sync_run_ai_settings(run)
        item.provider = ai_cfg.ai_provider
        item.model = ai_cfg.active_model()
        _log(run, f"Target {target.name}: AI Settings → {ai_cfg.ai_provider}/{ai_cfg.active_model()}")
        tool_ids = enabled_tool_ids(run.tools)
        if tool_ids:
            _log(
                run,
                f"Target {target.name}: tools={','.join(tool_ids)} → Full AI "
                f"(timeout {run.timeout_seconds}s)",
            )
        else:
            _log(run, f"Starting Full AI on {target.name} (timeout {run.timeout_seconds}s)")
        _start_tools_then_full_ai(run, session_id)

        deadline = started + run.timeout_seconds
        while time.monotonic() < deadline:
            if run.stop_requested:
                _stop_full_ai(session_id)
                item.status = "skipped"
                item.message = "Stopped by user"
                break
            if root_won_by_session.get(session_id):
                item.status = "passed"
                item.message = "Root achieved"
                _stop_full_ai(session_id)
                break
            if full_ai_finished_by_session.get(session_id) and not root_won_by_session.get(session_id):
                item.status = "failed"
                item.message = item.message or "Full AI finished without root"
                break
            time.sleep(0.5)
        else:
            _stop_full_ai(session_id)
            # Give the loop a moment to notice the stop flag
            time.sleep(1.0)
            if root_won_by_session.get(session_id):
                item.status = "passed"
                item.message = "Root achieved"
            else:
                item.status = "failed"
                item.message = f"Timeout after {run.timeout_seconds}s"

    except Exception as exc:  # noqa: BLE001
        item.status = "error"
        item.message = str(exc)
        _log(run, f"Target {target.name} error: {exc}")
    finally:
        if item.session_id:
            try:
                _stop_full_ai(item.session_id)
            except Exception:  # noqa: BLE001
                pass
            try:
                _disconnect_session(item.session_id)
            except Exception:  # noqa: BLE001
                pass
            try:
                reset_session_log_dir(item.session_id)
            except Exception:  # noqa: BLE001
                pass
        item.elapsed_seconds = round(time.monotonic() - started, 3)
        item.finished_at = _utcnow()
        _log(
            run,
            f"Target {target.name} → {item.status} ({item.elapsed_seconds}s) {item.message}",
        )
        if run.log_dir:
            try:
                write_benchmark_suite_snapshot(
                    Path(run.log_dir),
                    {
                        **run.to_public_dict(),
                        "suite_dir": run.log_dir,
                        "updated_at": _utcnow(),
                    },
                )
            except Exception:  # noqa: BLE001
                pass


# Optional batch results folder for multi-run suites (set by batch worker).
run_batch_dir: Optional[str] = None


def _selected_suite_targets(run: BenchmarkRun) -> List[BenchmarkTarget]:
    """Targets included in this run (subset of TARGETS)."""
    wanted = {item.target_id for item in run.targets}
    return [t for t in TARGETS if t.id in wanted]


def _worker(run: BenchmarkRun) -> None:
    try:
        def log_fn(msg: str) -> None:
            _log(run, msg)

        selected = _selected_suite_targets(run)

        # Benchmark labs always live on a remote host (Ansible + host networking).
        assert run.remote
        expected_host = str(run.remote["host"])

        run.phase = "deploying"
        target_names = ", ".join(t.id for t in selected)
        _log(run, f"Ensuring benchmark targets on {expected_host}: {target_names}")
        run.host = ensure_remote_benchmark(
            RemoteDeployConfig(
                host=run.remote["host"],
                username=run.remote["username"],
                password=run.remote["password"],
                port=int(run.remote.get("port") or 22),
            ),
            log=log_fn,
            targets=selected,
        )

        run.phase = "running"
        target_by_id = {t.id: t for t in selected}
        for item in run.targets:
            if run.stop_requested:
                item.status = "skipped"
                item.message = "Stopped before start"
                continue
            target = target_by_id[item.target_id]
            _run_target(run, item, target)

        run.phase = "done" if not run.stop_requested else "done"
        run.error = None
    except Exception as exc:  # noqa: BLE001
        run.phase = "error"
        run.error = str(exc)
        _log(run, f"Benchmark failed: {exc}")
    finally:
        run.finished_at = _utcnow()
        # Final provider/model from AI Settings (may differ per target).
        try:
            _sync_run_ai_settings(run)
        except Exception:  # noqa: BLE001
            pass
        with _lock:
            _history.append(
                deepcopy(
                    build_result_document(
                        run.to_public_dict(),
                        settings={"provider": run.provider, "model": run.model},
                    )
                )
            )
        if run.log_dir:
            try:
                write_benchmark_suite_snapshot(
                    Path(run.log_dir),
                    {
                        **run.to_public_dict(),
                        "suite_dir": run.log_dir,
                        "finished_at": run.finished_at,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                debug_logger.warning(f"[benchmark] failed to write run.json: {exc}")
            debug_logger.info(
                f"[benchmark] suite finished — full details in {run.log_dir}/ "
                f"(run.json, run.log, per-target events.jsonl)"
            )
        try:
            result_path = write_benchmark_result(
                run.to_public_dict(),
                settings={"provider": run.provider, "model": run.model},
                batch_dir=Path(run_batch_dir) if run_batch_dir else None,
            )
            run.result_dir = str(result_path.parent)
            _log(run, f"Results written → {result_path}")
            try:
                result_doc = json.loads(result_path.read_text(encoding="utf-8"))
                for issue in result_doc.get("issues") or []:
                    _log(run, f"Result issue: {issue}")
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001
            debug_logger.exception(f"[benchmark] failed to write results: {exc}")
            _log(run, f"Failed to write results: {exc}")
        _log(run, f"Benchmark finished (phase={run.phase})")


def _make_run(
    *,
    mode: str,
    timeout_seconds: int,
    tools_cfg: Dict[str, bool],
    merged_remote: Optional[Dict[str, Any]],
    batch_id: str,
    repetition: int,
    repetitions: int,
    suite_targets: List[BenchmarkTarget],
) -> BenchmarkRun:
    settings = _reload_ai_settings()
    run = BenchmarkRun(
        id=str(uuid.uuid4()),
        mode=mode,
        timeout_seconds=max(10, int(timeout_seconds or DEFAULT_TIMEOUT_SECONDS)),
        remote=merged_remote,
        tools=tools_cfg,
        targets=[
            TargetRunResult(
                target_id=t.id,
                name=t.name,
                port=t.port,
            )
            for t in suite_targets
        ],
        batch_id=batch_id,
        repetition=repetition,
        repetitions=repetitions,
        provider=settings.ai_provider,
        model=settings.active_model(),
    )
    suite_dir = begin_benchmark_suite_logs(
        run.id,
        mode=mode,
        meta={
            "timeout_seconds": run.timeout_seconds,
            "tools": tools_cfg,
            "targets": [t.id for t in suite_targets],
            "batch_id": batch_id,
            "repetition": repetition,
            "repetitions": repetitions,
            "provider": run.provider,
            "model": run.model,
        },
    )
    run.log_dir = str(suite_dir)
    return run


def start_run(
    *,
    mode: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    remote: Optional[Dict[str, Any]] = None,
    tools: Optional[Any] = None,
    repetitions: int = 1,
    run_plan: Optional[List[Any]] = None,
    target_ids: Optional[List[str]] = None,
) -> BenchmarkRun:
    global _current, run_batch_dir

    preset = load_remote_config()
    # Local docker-compose deploy was removed; always Ansible → remote lab host.
    mode = "remote"

    if timeout_seconds is None:
        timeout_seconds = int(preset.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)

    try:
        plan = normalize_run_plan(run_plan, repetitions=repetitions)
    except ValueError as exc:
        raise ValueError(str(exc)) from None
    slots = flatten_run_plan(plan)
    total_runs = len(slots)
    plan_desc = describe_run_plan(plan)

    # UI tools override JSON tools when provided; else JSON / defaults (BeRoot on).
    if tools is None:
        tools_cfg = normalize_tools(preset.get("tools"))
    else:
        tools_cfg = normalize_tools(tools)

    # Explicit empty list means "nothing selected" — reject instead of silently using all.
    if isinstance(target_ids, list) and len(target_ids) == 0:
        raise ValueError("Select at least one benchmark target")
    try:
        suite_targets = resolve_targets(target_ids)
    except ValueError:
        raise
    if not suite_targets:
        raise ValueError("Select at least one benchmark target")

    merged_remote = merge_remote_override(remote)
    if not merged_remote.get("host") or not merged_remote.get("username") or not merged_remote.get("password"):
        raise ValueError(
            "remote host, username, and password are required "
            "(set them in data/benchmark/remote.json or the Benchmark UI)"
        )

    required = (
        "flask_app",
        "socketio",
        "open_ssh_connection",
        "close_ssh_connection",
        "start_shell_listener",
        "autonomous",
        "execute_beroot",
        "prompts",
        "prompt_delimiters",
        "stop_full_ai_by_session",
        "loop",
        "emit_session",
    )
    missing = [k for k in required if k not in _hooks]
    if missing:
        raise RuntimeError(f"Benchmark hooks not registered: {', '.join(missing)}")

    first_entry, _, _ = slots[0]
    ai_cfg = apply_plan_entry_model(first_entry)

    with _lock:
        if _batch.get("active") or (_current and _current.phase not in {"done", "error"}):
            raise RuntimeError("A benchmark run is already in progress")
        batch_id = str(uuid.uuid4())
        _batch.update(
            {
                "active": True,
                "id": batch_id,
                "repetition": 1,
                "repetitions": total_runs,
                "run_plan": plan_desc,
                "current_provider": ai_cfg.ai_provider,
                "current_model": ai_cfg.active_model(),
                "stop": False,
            }
        )
        first = _make_run(
            mode=mode,
            timeout_seconds=timeout_seconds,
            tools_cfg=tools_cfg,
            merged_remote=merged_remote,
            batch_id=batch_id,
            repetition=1,
            repetitions=total_runs,
            suite_targets=suite_targets,
        )
        _current = first

    enabled = enabled_tool_ids(tools_cfg)
    selected_ids = [t.id for t in suite_targets]
    debug_logger.info(
        f"[benchmark] suite logs → {first.log_dir}/ "
        f"(run.log + per-target events under <target_id>/) "
        f"runs={total_runs} batch={batch_id[:8]} targets={selected_ids}"
    )
    _log(
        first,
        f"Benchmark queued (mode={mode}, tools={enabled or ['full_ai_only']}, "
        f"targets={selected_ids}, timeout={first.timeout_seconds}s, "
        f"ai={ai_cfg.ai_provider}/{ai_cfg.active_model()}, "
        f"run={1}/{total_runs}, logs={first.log_dir})",
    )

    def _batch_worker() -> None:
        global _current, run_batch_dir
        batch_folder: Optional[Path] = None
        completed_docs: List[Dict[str, Any]] = []
        try:
            if total_runs > 1:
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                batch_folder = BENCHMARK_RESULTS_DIR / f"batch_{stamp}_{batch_id[:8]}"
                batch_folder.mkdir(parents=True, exist_ok=True)
                run_batch_dir = str(batch_folder)
            else:
                run_batch_dir = None

            for global_idx, (entry, within_idx, entry_idx) in enumerate(slots, start=1):
                ai_cfg = apply_plan_entry_model(entry)
                with _lock:
                    if _batch.get("stop"):
                        break
                    _batch["repetition"] = global_idx
                    _batch["current_provider"] = ai_cfg.ai_provider
                    _batch["current_model"] = ai_cfg.active_model()
                    if global_idx == 1:
                        run = first
                        run.provider = ai_cfg.ai_provider
                        run.model = ai_cfg.active_model()
                    else:
                        run = _make_run(
                            mode=mode,
                            timeout_seconds=timeout_seconds,
                            tools_cfg=tools_cfg,
                            merged_remote=merged_remote,
                            batch_id=batch_id,
                            repetition=global_idx,
                            repetitions=total_runs,
                            suite_targets=suite_targets,
                        )
                        _current = run
                        _log(
                            run,
                            f"Benchmark queued (mode={mode}, tools={enabled or ['full_ai_only']}, "
                            f"targets={selected_ids}, timeout={run.timeout_seconds}s, "
                            f"ai={ai_cfg.ai_provider}/{ai_cfg.active_model()}, "
                            f"run={global_idx}/{total_runs} "
                            f"(plan entry {entry_idx + 1}, loop {within_idx}/{entry.repetitions}), "
                            f"logs={run.log_dir})",
                        )
                debug_logger.info(
                    f"[benchmark] starting run {global_idx}/{total_runs} "
                    f"model={ai_cfg.ai_provider}/{ai_cfg.active_model()} run_id={run.id}"
                )
                _worker(run)
                # Capture result document path from run
                if run.result_dir:
                    try:
                        result_json = Path(run.result_dir) / "result.json"
                        if result_json.is_file():
                            completed_docs.append(
                                json.loads(result_json.read_text(encoding="utf-8"))
                            )
                    except Exception:  # noqa: BLE001
                        completed_docs.append(run.to_public_dict())
                else:
                    completed_docs.append(run.to_public_dict())
                with _lock:
                    if _batch.get("stop"):
                        break
        finally:
            if batch_folder is not None and completed_docs:
                try:
                    write_batch_summary(
                        batch_folder, batch_id=batch_id, runs=completed_docs
                    )
                except Exception as exc:  # noqa: BLE001
                    debug_logger.warning(f"[benchmark] batch summary failed: {exc}")
            with _lock:
                _batch["active"] = False
                _batch["stop"] = False
            run_batch_dir = None
            try:
                get_settings_manager().reload()
            except Exception:  # noqa: BLE001
                pass
            debug_logger.info(
                f"[benchmark] batch finished id={batch_id[:8]} "
                f"completed={len(completed_docs)}/{total_runs}"
            )

    thread = threading.Thread(
        target=_batch_worker,
        name=f"benchmark-batch-{batch_id[:8]}",
        daemon=True,
    )
    thread.start()
    return first
