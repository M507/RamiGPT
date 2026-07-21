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
from typing import Any, Callable, Dict, List, Optional, Tuple

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
    DEFAULT_TARGET_PROFILE_ID,
    DEFAULT_TIMEOUT_SECONDS,
    TARGETS,
    BenchmarkTarget,
    get_default_target_ids,
    get_profile,
    list_profiles,
    resolve_profile_for_target_ids,
    resolve_targets,
)
from ramigpt.benchmark.batch_plan import (
    BatchSlot,
    describe_batch_plan,
    normalize_batch_plans,
)
from ramigpt.benchmark.model_warmup import ModelWarmupResult, warmup_ai_model
from ramigpt.benchmark.hardware import resolve_benchmark_hardware
from ramigpt.benchmark.profile import collaborative_profile_key, profile_display_label
from ramigpt.benchmark.model_registry import resolve_model_identity
from ramigpt.benchmark.results import (
    build_result_document,
    enrich_target_from_events,
    write_batch_summary,
    write_benchmark_result,
)
from ramigpt.benchmark.role_plan import apply_plan_entry_role
from ramigpt.benchmark.run_plan import apply_plan_entry_model
from ramigpt.benchmark.tools import (
    AVAILABLE_TOOLS,
    default_tools,
    enabled_tool_ids,
    normalize_tools,
    pick_benchmark_tool,
)
from ramigpt.config import Settings, get_settings, get_settings_manager
from ramigpt.config.settings import load_role_objectives
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
    role_objective: str = ""
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
    role_objective: str = ""
    model_key_name: str = ""
    profile_key: str = ""
    profile_label: str = ""
    suite_profile_id: str = ""
    suite_profile_name: str = ""
    model_registry: Optional[Dict[str, Any]] = None
    hardware: Optional[Dict[str, Any]] = None
    result_dir: Optional[str] = None
    model_warmup: Optional[Dict[str, Any]] = None

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
    "role_plan": None,
    "current_provider": "",
    "current_model": "",
    "current_role": "",
    "stop": False,
}
# Completed runs awaiting explicit "Save collab results" from the UI.
_pending_collab: Dict[str, Any] = {
    "batch_id": None,
    "batch_meta": None,
    "runs": {},
}


def _result_settings(run: BenchmarkRun) -> Dict[str, Any]:
    return {
        "provider": run.provider,
        "model": run.model,
        "model_key_name": run.model_key_name,
        "model_registry": run.model_registry,
        "hardware": run.hardware,
    }


def _clear_pending_collab() -> None:
    global _pending_collab
    _pending_collab = {"batch_id": None, "batch_meta": None, "runs": {}}


def clear_pending_collab() -> None:
    """Discard staged collab results that were never saved to disk."""
    with _lock:
        _clear_pending_collab()


def _stage_collab_result(run: BenchmarkRun) -> None:
    """Keep a completed run in memory until the user saves collab results."""
    settings = _result_settings(run)
    doc = build_result_document(run.to_public_dict(), settings=settings)
    with _lock:
        _history.append(deepcopy(doc))
        _pending_collab["runs"][run.id] = {
            "run_public": run.to_public_dict(),
            "settings": settings,
            "repetition": run.repetition,
        }
        if run.batch_id:
            _pending_collab["batch_id"] = run.batch_id
    _log(
        run,
        "Results ready — click Save collab results to persist under data/benchmark/results/",
    )


def save_collab_results() -> Dict[str, Any]:
    """Persist staged benchmark runs to data/benchmark/results/ and rebuild master."""
    with _lock:
        if _batch.get("active"):
            return {"ok": False, "error": "Wait for the benchmark to finish before saving"}
        pending = deepcopy(_pending_collab)
    runs_map = pending.get("runs") or {}
    if not runs_map:
        return {"ok": False, "error": "No unsaved benchmark results to save"}

    runs_sorted = sorted(
        runs_map.values(),
        key=lambda entry: int(entry.get("repetition") or 1),
    )
    batch_id = pending.get("batch_id")
    batch_dir: Optional[Path] = None
    if batch_id and len(runs_sorted) > 1:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        batch_dir = BENCHMARK_RESULTS_DIR / f"batch_{stamp}_{str(batch_id)[:8]}"

    paths: List[str] = []
    completed_docs: List[Dict[str, Any]] = []
    for entry in runs_sorted:
        result_path = write_benchmark_result(
            entry["run_public"],
            settings=entry["settings"],
            batch_dir=batch_dir,
        )
        paths.append(str(result_path))
        completed_docs.append(json.loads(result_path.read_text(encoding="utf-8")))
        run_id = entry["run_public"].get("id")
        result_parent = str(result_path.parent)
        with _lock:
            if _current and _current.id == run_id:
                _current.result_dir = result_parent

    batch_meta = pending.get("batch_meta") or {}
    if batch_dir is not None and batch_id and completed_docs:
        write_batch_summary(
            batch_dir,
            batch_id=str(batch_id),
            runs=completed_docs,
            model_plan=batch_meta.get("model_plan"),
            role_plan=batch_meta.get("role_plan"),
        )

    with _lock:
        _clear_pending_collab()

    return {
        "ok": True,
        "paths": paths,
        "batch_dir": str(batch_dir) if batch_dir else None,
        "run_count": len(paths),
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
                "role_plan": _batch.get("role_plan"),
                "current_provider": _batch.get("current_provider"),
                "current_model": _batch.get("current_model"),
                "current_role": _batch.get("current_role"),
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
                "target_ids": get_default_target_ids(),
                "default_profile_id": DEFAULT_TARGET_PROFILE_ID,
                "tools": remote_cfg.get("tools") or default_tools(),
            },
            "ai_settings": {
                "provider": get_settings().ai_provider,
                "model": get_settings().active_model(),
                "role_objective": get_settings().role_objective,
                "role_objective_options": list(load_role_objectives().keys()),
                "advanced_mode": get_settings().advanced_mode,
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
            "collab_save": {
                "pending": bool((_pending_collab.get("runs") or {})),
                "run_count": len(_pending_collab.get("runs") or {}),
                "batch_id": _pending_collab.get("batch_id"),
            },
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
    """Copy the active in-memory AI provider/model/role onto the run record."""
    cfg = settings or get_settings()
    run.provider = cfg.ai_provider
    run.model = cfg.active_model()
    run.role_objective = cfg.role_objective
    return cfg


def _format_slot_plan(slot: BatchSlot) -> str:
    return (
        f"model entry {slot.model_entry_idx + 1} loop {slot.model_rep}/"
        f"{slot.model_entry.repetitions}, role entry {slot.role_entry_idx + 1} loop "
        f"{slot.role_rep}/{slot.role_entry.repetitions}"
    )


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


def _log_model_warmup(run: BenchmarkRun, warm: ModelWarmupResult) -> None:
    for line in warm.log_lines:
        _log(run, line)
    run.model_warmup = warm.to_dict()


def _finish_warmup_failed_run(run: BenchmarkRun, warm: ModelWarmupResult) -> None:
    run.phase = "error"
    run.error = warm.error or "AI model warmup failed"
    run.finished_at = _utcnow()
    for item in run.targets:
        item.status = "skipped"
        item.message = "Skipped — model warmup failed"
        item.finished_at = run.finished_at
    try:
        _attach_run_model_identity(run)
    except Exception:  # noqa: BLE001
        pass
    result_settings = _result_settings(run)
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
        except Exception:  # noqa: BLE001
            pass
    _stage_collab_result(run)


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
    Run one enabled pre-tool first (BeRoot or LinEnum with AI on → Full AI loop),
    or plain Full AI when no tools are selected.

    When multiple tools are checked, ``TOOL_RUN_ORDER`` picks a single runner
    (BeRoot before LinEnum).
    """
    enabled = enabled_tool_ids(run.tools)
    tool_id = pick_benchmark_tool(run.tools)
    if len(enabled) > 1 and tool_id:
        skipped = [t for t in enabled if t != tool_id]
        _log(
            run,
            f"Multiple pre-tools selected {enabled!r} — running {tool_id!r} only "
            f"(skipped: {', '.join(skipped)})",
        )
    root_won_by_session[session_id] = False
    full_ai_finished_by_session[session_id] = False
    stop_flags = _hooks["stop_full_ai_by_session"]
    flag = stop_flags.setdefault(session_id, threading.Event())
    flag.clear()
    loop = _hooks["loop"]
    loop[session_id] = 1

    session_data = _session_data(session_id)
    session_data["with_ai"] = True
    session_data["from_benchmark"] = True
    session_data["use_os_thread"] = True

    if tool_id == "beroot":
        execute_beroot = _hooks.get("execute_beroot")
        if not callable(execute_beroot):
            raise RuntimeError("execute_beroot hook not registered")
        _log(run, "Running BeRoot (AI on) — scan then Full AI until root")
        with _lock:
            for item in run.targets:
                if item.session_id == session_id and "beroot" not in item.tools_used:
                    item.tools_used.append("beroot")
        try:
            execute_beroot(session_data)
        except Exception as exc:  # noqa: BLE001
            mark_full_ai_finished(session_id, stop_reason=f"BeRoot failed: {exc}")
            raise
        if not full_ai_finished_by_session.get(session_id) and loop.get(session_id) == 0:
            if not root_won_by_session.get(session_id):
                mark_full_ai_finished(session_id)
        return

    if tool_id == "linenum":
        execute_linenum = _hooks.get("execute_linenum")
        if not callable(execute_linenum):
            raise RuntimeError("execute_linenum hook not registered")
        _log(run, "Running LinEnum (AI on) — scan then Full AI until root")
        with _lock:
            for item in run.targets:
                if item.session_id == session_id and "linenum" not in item.tools_used:
                    item.tools_used.append("linenum")
        try:
            execute_linenum(session_data)
        except Exception as exc:  # noqa: BLE001
            mark_full_ai_finished(session_id, stop_reason=f"LinEnum failed: {exc}")
            raise
        if not full_ai_finished_by_session.get(session_id) and loop.get(session_id) == 0:
            if not root_won_by_session.get(session_id):
                mark_full_ai_finished(session_id)
        return

    if tool_id == "linpeas":
        execute_linpeas = _hooks.get("execute_linpeas")
        if not callable(execute_linpeas):
            raise RuntimeError("execute_linpeas hook not registered")
        _log(run, "Running LinPEAS (AI on) — scan then Full AI until root")
        with _lock:
            for item in run.targets:
                if item.session_id == session_id and "linpeas" not in item.tools_used:
                    item.tools_used.append("linpeas")
        try:
            execute_linpeas(session_data)
        except Exception as exc:  # noqa: BLE001
            mark_full_ai_finished(session_id, stop_reason=f"LinPEAS failed: {exc}")
            raise
        if not full_ai_finished_by_session.get(session_id) and loop.get(session_id) == 0:
            if not root_won_by_session.get(session_id):
                mark_full_ai_finished(session_id)
        return

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
        planned_provider, planned_model = run.provider, run.model
        planned_role = run.role_objective
        ai_cfg = _sync_run_ai_settings(run)
        item.provider = ai_cfg.ai_provider
        item.model = ai_cfg.active_model()
        item.role_objective = ai_cfg.role_objective
        if (item.provider, item.model) != (planned_provider, planned_model):
            _log(
                run,
                f"Target {target.name}: WARNING model drift "
                f"(queued {planned_provider}/{planned_model} → active {item.provider}/{item.model})",
            )
        if item.role_objective != planned_role and planned_role:
            _log(
                run,
                f"Target {target.name}: WARNING role drift "
                f"(queued {planned_role} → active {item.role_objective})",
            )
        _log(
            run,
            f"Target {target.name}: AI Settings → {ai_cfg.ai_provider}/"
            f"{ai_cfg.active_model()} · role={ai_cfg.role_objective}",
        )
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
        item.message = str(exc) or f"{type(exc).__name__}"
        _log(run, f"Target {target.name} error: {item.message}")
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


def _attach_run_model_identity(run: BenchmarkRun) -> None:
    """Resolve registry key_name + hardware profile for this run."""
    cfg = get_settings()
    try:
        cfg = _sync_run_ai_settings(run, cfg)
    except Exception:  # noqa: BLE001
        pass
    run.hardware = resolve_benchmark_hardware(provider=run.provider)
    try:
        identity = resolve_model_identity(get_settings())
        run.model_key_name = str(identity.get("key_name") or "")
        run.model_registry = identity
        fp = identity.get("fingerprint") or {}
        detail_bits = [
            str(fp.get("parameter_size") or "").strip(),
            str(fp.get("quantization_level") or "").strip(),
        ]
        detail_txt = " · ".join(bit for bit in detail_bits if bit)
        _log(
            run,
            "Model identity "
            f"{run.model_key_name} ({run.provider}/{run.model}"
            f"{(' · ' + detail_txt) if detail_txt else ''}) "
            f"→ {identity.get('registry_path') or '?'}",
        )
        for issue in identity.get("issues") or []:
            _log(run, f"Model registry note: {issue}")
    except Exception as exc:  # noqa: BLE001
        run.model_key_name = ""
        run.model_registry = {
            "key_name": "",
            "provider": run.provider,
            "model": run.model,
            "issues": [str(exc)],
        }
        _log(run, f"Model registry failed: {exc}")
    run.profile_key = collaborative_profile_key(
        run.model_key_name,
        run.provider,
        run.model,
        run.hardware or {},
    )
    run.profile_label = profile_display_label(
        run.model_key_name,
        run.hardware or {},
        provider=run.provider,
        model=run.model,
    )
    if run.profile_label:
        _log(run, f"Benchmark profile: {run.profile_label}")
    if not run.hardware:
        _log(run, "Benchmark hardware profile not configured (.env BENCHMARK_GPU_*)")
    elif (run.provider or "").strip().lower() == "openwebui":
        _log(run, "Benchmark hardware profile: Online AI Service (Open WebUI proxy)")


def _worker(run: BenchmarkRun) -> None:
    try:
        _attach_run_model_identity(run)
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
        _stage_collab_result(run)
        _log(run, f"Benchmark finished (phase={run.phase})")


def _resolve_suite_profile(
    *,
    target_ids: List[str],
    suite_profile_id: Optional[str],
) -> tuple[str, str]:
    profile = None
    if suite_profile_id:
        try:
            profile = get_profile(str(suite_profile_id).strip())
        except KeyError:
            profile = None
    if profile is None:
        profile = resolve_profile_for_target_ids(target_ids)
    if profile is None:
        return "", ""
    return profile.id, profile.name


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
    suite_profile_id: str = "",
    suite_profile_name: str = "",
) -> BenchmarkRun:
    settings = get_settings()
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
        role_objective=settings.role_objective,
        suite_profile_id=suite_profile_id,
        suite_profile_name=suite_profile_name,
    )
    suite_dir = begin_benchmark_suite_logs(
        run.id,
        mode=mode,
        meta={
            "timeout_seconds": run.timeout_seconds,
            "tools": tools_cfg,
            "targets": [t.id for t in suite_targets],
            "suite_profile_id": run.suite_profile_id,
            "suite_profile_name": run.suite_profile_name,
            "batch_id": batch_id,
            "repetition": repetition,
            "repetitions": repetitions,
            "provider": run.provider,
            "model": run.model,
            "role_objective": run.role_objective,
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
    role_plan: Optional[List[Any]] = None,
    role_repetitions: int = 1,
    target_ids: Optional[List[str]] = None,
    suite_profile_id: Optional[str] = None,
) -> BenchmarkRun:
    global _current, run_batch_dir

    preset = load_remote_config()
    # Local docker-compose deploy was removed; always Ansible → remote lab host.
    mode = "remote"

    if timeout_seconds is None:
        timeout_seconds = int(preset.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)

    try:
        model_plan, role_plan_entries, slots = normalize_batch_plans(
            run_plan=run_plan,
            role_plan=role_plan,
            repetitions=repetitions,
            role_repetitions=role_repetitions,
        )
    except ValueError as exc:
        raise ValueError(str(exc)) from None
    total_runs = len(slots)
    plan_desc = describe_batch_plan(model_plan, role_plan_entries)

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

    selected_ids = [t.id for t in suite_targets]
    suite_sp_id, suite_sp_name = _resolve_suite_profile(
        target_ids=selected_ids,
        suite_profile_id=suite_profile_id,
    )

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
        "execute_linenum",
        "execute_linpeas",
        "prompts",
        "prompt_delimiters",
        "stop_full_ai_by_session",
        "loop",
        "emit_session",
    )
    missing = [k for k in required if k not in _hooks]
    if missing:
        raise RuntimeError(f"Benchmark hooks not registered: {', '.join(missing)}")

    first_slot = slots[0]
    ai_cfg = apply_plan_entry_model(first_slot.model_entry)
    role_cfg = apply_plan_entry_role(first_slot.role_entry)

    with _lock:
        if _batch.get("active") or (_current and _current.phase not in {"done", "error"}):
            raise RuntimeError("A benchmark run is already in progress")
        if _pending_collab.get("runs"):
            debug_logger.info(
                "[benchmark] discarding unsaved collab results from a previous run"
            )
            _clear_pending_collab()
        batch_id = str(uuid.uuid4())
        _batch.update(
            {
                "active": True,
                "id": batch_id,
                "repetition": 1,
                "repetitions": total_runs,
                "run_plan": plan_desc.get("model_plan"),
                "role_plan": plan_desc.get("role_plan"),
                "current_provider": ai_cfg.ai_provider,
                "current_model": ai_cfg.active_model(),
                "current_role": role_cfg.role_objective,
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
            suite_profile_id=suite_sp_id,
            suite_profile_name=suite_sp_name,
        )
        first.provider = ai_cfg.ai_provider
        first.model = ai_cfg.active_model()
        first.role_objective = role_cfg.role_objective
        _current = first

    enabled = enabled_tool_ids(tools_cfg)
    debug_logger.info(
        f"[benchmark] suite logs → {first.log_dir}/ "
        f"(run.log + per-target events under <target_id>/) "
        f"runs={total_runs} batch={batch_id[:8]} targets={selected_ids}"
    )
    profile_note = f", profile={suite_sp_name}" if suite_sp_name else ""
    _log(
        first,
        f"Benchmark queued (mode={mode}, tools={enabled or ['full_ai_only']}, "
        f"targets={selected_ids}, timeout={first.timeout_seconds}s, "
        f"ai={ai_cfg.ai_provider}/{ai_cfg.active_model()}, "
        f"role={role_cfg.role_objective}{profile_note}, "
        f"run={1}/{total_runs} ({_format_slot_plan(first_slot)}), logs={first.log_dir})",
    )
    if total_runs > 1:
        _log(
            first,
            f"Batch plan ({total_runs} runs, model-major → role-major): "
            f"{plan_desc.get('model_entry_count')} model entries, "
            f"{plan_desc.get('role_entry_count')} role entries",
        )

    def _batch_worker() -> None:
        global _current, run_batch_dir
        completed_docs: List[Dict[str, Any]] = []
        try:
            run_batch_dir = None

            last_warm: Optional[Tuple[str, str]] = None

            for global_idx, slot in enumerate(slots, start=1):
                ai_cfg = apply_plan_entry_model(slot.model_entry)
                role_cfg = apply_plan_entry_role(slot.role_entry)
                with _lock:
                    if _batch.get("stop"):
                        break
                    _batch["repetition"] = global_idx
                    _batch["current_provider"] = ai_cfg.ai_provider
                    _batch["current_model"] = ai_cfg.active_model()
                    _batch["current_role"] = role_cfg.role_objective
                    if global_idx == 1:
                        run = first
                        run.provider = ai_cfg.ai_provider
                        run.model = ai_cfg.active_model()
                        run.role_objective = role_cfg.role_objective
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
                            suite_profile_id=suite_sp_id,
                            suite_profile_name=suite_sp_name,
                        )
                        run.provider = ai_cfg.ai_provider
                        run.model = ai_cfg.active_model()
                        run.role_objective = role_cfg.role_objective
                        _current = run
                        _log(
                            run,
                            f"Benchmark queued (mode={mode}, tools={enabled or ['full_ai_only']}, "
                            f"targets={selected_ids}, timeout={run.timeout_seconds}s, "
                            f"ai={ai_cfg.ai_provider}/{ai_cfg.active_model()}, "
                            f"role={role_cfg.role_objective}, "
                            f"run={global_idx}/{total_runs} ({_format_slot_plan(slot)}), "
                            f"logs={run.log_dir})",
                        )

                warm = warmup_ai_model(ai_cfg, last_warm=last_warm)
                _log_model_warmup(run, warm)
                if not warm.ok:
                    _finish_warmup_failed_run(run, warm)
                    completed_docs.append(run.to_public_dict())
                    with _lock:
                        if _batch.get("stop"):
                            break
                    continue
                if not warm.skipped:
                    last_warm = (ai_cfg.ai_provider, ai_cfg.active_model())

                debug_logger.info(
                    f"[benchmark] starting run {global_idx}/{total_runs} "
                    f"model={ai_cfg.ai_provider}/{ai_cfg.active_model()} "
                    f"role={role_cfg.role_objective} run_id={run.id}"
                )
                _worker(run)
                completed_docs.append(
                    build_result_document(
                        run.to_public_dict(),
                        settings=_result_settings(run),
                    )
                )
                with _lock:
                    if _batch.get("stop"):
                        break
        finally:
            if total_runs > 1 and completed_docs:
                with _lock:
                    _pending_collab["batch_meta"] = {
                        "model_plan": _batch.get("run_plan"),
                        "role_plan": _batch.get("role_plan"),
                    }
            with _lock:
                _batch["active"] = False
                _batch["stop"] = False
            run_batch_dir = None
            try:
                get_settings_manager().reload()
            except Exception:  # noqa: BLE001
                pass
            for doc in completed_docs:
                debug_logger.info(
                    f"[benchmark] batch run {doc.get('repetition')}/{total_runs}: "
                    f"{doc.get('provider')}/{doc.get('model')} "
                    f"role={doc.get('role_objective') or '?'}"
                )
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
