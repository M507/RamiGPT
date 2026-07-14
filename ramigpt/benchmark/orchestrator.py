"""Orchestrate deploy → SSH sessions → Full AI → pass/fail with timeout."""

from __future__ import annotations

import threading
import time
import uuid
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from flask import Flask

from ramigpt.benchmark.deploy import (
    RemoteDeployConfig,
    check_target_ports,
    deploy_local,
    deploy_remote,
)
from ramigpt.benchmark.remote_config import load_remote_config, merge_remote_override, public_remote_config
from ramigpt.benchmark.targets import (
    BENCH_GROUP_ID,
    BENCH_PASSWORD,
    BENCH_USERNAME,
    DEFAULT_TIMEOUT_SECONDS,
    TARGETS,
    BenchmarkTarget,
)
from ramigpt.benchmark.tools import AVAILABLE_TOOLS, default_tools, enabled_tool_ids, normalize_tools
from ramigpt.domain import PrivEscPrompt
from ramigpt.services.runtime_status import set_status
from ramigpt.services.session_store import get_session_store
from ramigpt.utils import debug_logger

# Filled by web layer so the orchestrator can reuse live SSH / Full AI primitives.
_hooks: Dict[str, Any] = {}


def register_benchmark_hooks(**kwargs: Any) -> None:
    """Inject runtime dependencies from ramigpt.web.app (SSH shells, autonomous, …)."""
    _hooks.update(kwargs)


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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BenchmarkRun:
    id: str
    mode: str  # local | remote
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


def mark_root_won(session_id: str) -> None:
    root_won_by_session[session_id] = True


def mark_full_ai_finished(session_id: str) -> None:
    full_ai_finished_by_session[session_id] = True


def get_current_run() -> Optional[BenchmarkRun]:
    with _lock:
        return _current


def get_status() -> Dict[str, Any]:
    with _lock:
        run = _current
        remote_cfg = public_remote_config()
        return {
            "running": bool(run and run.phase not in {"done", "error"}),
            "run": run.to_public_dict() if run else None,
            "targets": [t.to_dict() for t in TARGETS],
            "defaults": {
                "timeout_seconds": int(
                    remote_cfg.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS
                ),
                "username": BENCH_USERNAME,
                "password": BENCH_PASSWORD,
                "ports": [t.port for t in TARGETS],
                "tools": remote_cfg.get("tools") or default_tools(),
            },
            "available_tools": AVAILABLE_TOOLS,
            "remote_preset": remote_cfg,
            "history": list(_history[-10:]),
        }


def request_stop() -> Dict[str, Any]:
    with _lock:
        if not _current or _current.phase in {"done", "error"}:
            return {"ok": False, "error": "No active benchmark run"}
        _current.stop_requested = True
        _current.phase = "stopping"
        _current.log.append(f"[{_utcnow()}] Stop requested")
        stop_flags = _hooks.get("stop_full_ai_by_session") or {}
        for item in _current.targets:
            if item.session_id and item.session_id in stop_flags:
                stop_flags[item.session_id].set()
        return {"ok": True, "run": _current.to_public_dict()}


def _log(run: BenchmarkRun, message: str) -> None:
    line = f"[{_utcnow()}] {message}"
    run.log.append(line)
    debug_logger.info(f"[benchmark] {message}")
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

        priv = PrivEscPrompt(
            saved.username,
            flask_session["password"],
            f"{saved.username}@{saved.host}",
            saved.hostname or "pehost",
        )
        for fact in saved.facts:
            priv.add_facts(fact)
        for hint in saved.hints:
            priv.add_hint(hint)
        for avoid in saved.avoids:
            priv.add_avoid(avoid)
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
    flask_app: Flask = _hooks["flask_app"]
    store = get_session_store()
    saved = store.get_session(session_id)
    stop_flags = _hooks["stop_full_ai_by_session"]
    socketio = _hooks["socketio"]
    autonomous = _hooks["autonomous"]
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
    }

    def _runner() -> None:
        with flask_app.app_context():
            try:
                autonomous(session_data)
            finally:
                mark_full_ai_finished(session_id)

    socketio.start_background_task(_runner)


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
        # Blocking: scan completes here; Full AI continues in a background task.
        try:
            execute_beroot(session_data)
        except Exception as exc:  # noqa: BLE001
            mark_full_ai_finished(session_id)
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

    try:
        session_id = _upsert_session_for_target(target, run.host)
        item.session_id = session_id
        _connect_session(session_id)
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
                # Autonomous exited without root (max requests / error)
                item.status = "failed"
                item.message = "Full AI finished without root"
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
        item.elapsed_seconds = round(time.monotonic() - started, 3)
        item.finished_at = _utcnow()
        _log(
            run,
            f"Target {target.name} → {item.status} ({item.elapsed_seconds}s) {item.message}",
        )


def _worker(run: BenchmarkRun) -> None:
    try:
        run.phase = "deploying"
        _log(run, f"Deploying benchmark targets ({run.mode})")

        def log_fn(msg: str) -> None:
            _log(run, msg)

        if run.mode == "local":
            run.host = deploy_local(log=log_fn)
        else:
            assert run.remote
            run.host = deploy_remote(
                RemoteDeployConfig(
                    host=run.remote["host"],
                    username=run.remote["username"],
                    password=run.remote["password"],
                    port=int(run.remote.get("port") or 22),
                ),
                log=log_fn,
            )

        ports = check_target_ports(run.host, log=log_fn)
        if not all(p["open"] for p in ports):
            missing = [f"{p['port']}" for p in ports if not p["open"]]
            raise RuntimeError(f"Benchmark SSH ports not open: {', '.join(missing)}")

        run.phase = "running"
        target_by_id = {t.id: t for t in TARGETS}
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
        with _lock:
            _history.append(deepcopy(run.to_public_dict()))
        _log(run, f"Benchmark finished (phase={run.phase})")


def start_run(
    *,
    mode: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    remote: Optional[Dict[str, Any]] = None,
    tools: Optional[Any] = None,
) -> BenchmarkRun:
    global _current

    preset = load_remote_config()
    mode = (mode or preset.get("mode") or "local").strip().lower()
    if mode not in {"local", "remote"}:
        raise ValueError("mode must be 'local' or 'remote'")

    if timeout_seconds is None:
        timeout_seconds = int(preset.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)

    # UI tools override JSON tools when provided; else JSON / defaults (BeRoot on).
    if tools is None:
        tools_cfg = normalize_tools(preset.get("tools"))
    else:
        tools_cfg = normalize_tools(tools)

    merged_remote: Optional[Dict[str, Any]] = None
    if mode == "remote":
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

    with _lock:
        if _current and _current.phase not in {"done", "error"}:
            raise RuntimeError("A benchmark run is already in progress")
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
                for t in TARGETS
            ],
        )
        _current = run

    enabled = enabled_tool_ids(tools_cfg)
    _log(
        run,
        f"Benchmark queued (mode={mode}, tools={enabled or ['full_ai_only']}, "
        f"timeout={run.timeout_seconds}s)",
    )

    thread = threading.Thread(target=_worker, args=(run,), name=f"benchmark-{run.id[:8]}", daemon=True)
    thread.start()
    return run
