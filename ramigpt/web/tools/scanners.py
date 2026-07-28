"""Background scanner tasks (BeRoot, LinEnum, LinPEAS) and Full AI handoff."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from ramigpt.config import get_settings
from ramigpt.paths import (
    BEROOT_DOWNLOADS_DIR,
    LINENUM_DOWNLOADS_DIR,
    LINPEAS_DOWNLOADS_DIR,
    ensure_runtime_dirs,
)
from ramigpt.tools.linenum import sanitize_linenum_for_prompt
from ramigpt.tools.linpeas import sanitize_linpeas_for_prompt
from ramigpt.utils import debug_logger, get_session_logger
from ramigpt.web.ai.tasks import start_autonomous_task
from ramigpt.web.extensions import app
from ramigpt.web.prompt_helpers import sanitize_beroot_for_prompt
from ramigpt.web.session_emit import emit_session
from ramigpt.web.tools.beroot import (
    _run_linenum_on_remote,
    _run_linpeas_on_remote,
    upload_and_run_beroot,
)
from ramigpt.web.state import (
    beroots,
    linenums,
    linpeas_reports,
    loop,
    prompts,
    root_won_by_session,
    ssh_shells,
    ssh_ssh_conns,
    stop_full_ai_by_session,
)

def _emit_tool_progress(session_id, tool_label, message, *, color="#58a6ff") -> None:
    emit_session(session_id, f"[{tool_label}] {message}", color=color)


def _record_benchmark_scan_result(session_data, *, ok: bool, error: str = "") -> None:
    """Report scan outcome to benchmark prefetch (scan-only runs pass ``scan_result``)."""
    result = session_data.get("scan_result")
    if not isinstance(result, dict):
        return
    result["ok"] = bool(ok)
    if error:
        result["error"] = error


def _handoff_scanner_to_full_ai(session_data, *, source: str, tool_label: str, slog) -> None:
    """After a pre-tool scan, optionally start the Full AI loop with findings in context."""
    session_id = session_data["sid"]
    with_ai = bool(session_data.get("with_ai", True))

    if not with_ai:
        loop[session_id] = 0
        emit_session(
            session_id,
            f"[{tool_label}] Done (AI off) — findings saved for later Full AI / Guide Me.",
            color="#8b949e",
        )
        return

    priv_esc = prompts.get(session_id)
    shell = ssh_shells.get(session_id)
    if priv_esc is None or shell is None:
        loop[session_id] = 0
        emit_session(
            session_id,
            f"[{tool_label}] Scan saved but cannot start Full AI (missing prompt or shell).",
            color="#f85149",
        )
        try:
            from ramigpt.benchmark.orchestrator import mark_full_ai_finished

            mark_full_ai_finished(
                session_id,
                stop_reason=f"{tool_label} failed: missing prompt or shell for Full AI handoff",
            )
        except Exception:
            pass
        return

    flag = stop_full_ai_by_session.setdefault(session_id, threading.Event())
    flag.clear()
    root_won_by_session[session_id] = False
    loop[session_id] = 1
    full_ai_event = f"{source.upper()}_FULL_AI"
    slog.event(full_ai_event, f"{tool_label} finished — starting Full AI loop with scanner findings")
    emit_session(
        session_id,
        f"[{tool_label}] Findings sent to Full AI — continuing with autonomous privilege escalation…",
        color="#58a6ff",
    )
    ai_cfg = get_settings()
    get_session_logger(session_id).event(
        "FULL_AI_REQUESTED",
        f"Full AI started after {tool_label} (AI checkbox)",
        hostname=session_data.get("hostname"),
        server=session_data.get("server"),
        port=session_data.get("port"),
        source=source,
        provider=ai_cfg.ai_provider,
        model=ai_cfg.active_model(),
    )
    start_autonomous_task(session_data)
def execute_beroot(session_data):
    """
    Background task: upload BeRoot to the target, run it, attach findings to the
    session prompt, then optionally hand off to Full AI (when with_ai=True).
    """
    with app.app_context():
        session_id = session_data["sid"]
        with_ai = bool(session_data.get("with_ai", True))
        slog = get_session_logger(session_id)
        ssh_conn = ssh_ssh_conns.get(session_id)

        if ssh_conn is None:
            emit_session(session_id, "[BeRoot] No SSH connection — connect first.", color="#f85149")
            loop[session_id] = 0
            _record_benchmark_scan_result(
                session_data,
                ok=False,
                error="BeRoot failed: no SSH connection",
            )
            if with_ai:
                try:
                    from ramigpt.benchmark.orchestrator import mark_full_ai_finished
                    mark_full_ai_finished(
                        session_id,
                        stop_reason="BeRoot failed: no SSH connection",
                    )
                except Exception:
                    pass
            return

        password = session_data.get("password") or ""
        slog.event(
            "BEROOT_START",
            "Uploading and running BeRoot on remote host",
            server=session_data.get("server"),
            port=session_data.get("port"),
            username=session_data.get("username"),
            with_ai=with_ai,
        )
        emit_session(
            session_id,
            f"[BeRoot] Uploading toolkit to /tmp/Linux … (AI={'on' if with_ai else 'off'})",
            color="#58a6ff",
        )
        _emit_tool_progress(session_id, "BeRoot", "Sending toolkit to remote host…")
        _emit_tool_progress(
            session_id,
            "BeRoot",
            "Executing scan on target — waiting for results (this may take a minute)…",
        )
        debug_logger.info(
            f"beroot.start session_id={session_id!r} "
            f"host={session_data.get('server')!r}:{session_data.get('port')} with_ai={with_ai}"
        )

        try:
            beroot_started = time.monotonic()
            beroot_string = upload_and_run_beroot(
                ssh_conn,
                password=password,
                slog=slog,
                timeout=180,
            )
            beroot_duration = round(time.monotonic() - beroot_started, 3)
        except Exception as exc:  # noqa: BLE001
            debug_logger.exception(f"beroot.failed session_id={session_id!r}")
            slog.exception(f"beroot failed: {exc}")
            slog.event("BEROOT_FAILED", str(exc))
            emit_session(session_id, f"[BeRoot] Failed: {exc}", color="#f85149")
            loop[session_id] = 0
            _record_benchmark_scan_result(
                session_data,
                ok=False,
                error=f"BeRoot failed: {exc}",
            )
            if with_ai:
                try:
                    from ramigpt.benchmark.orchestrator import mark_full_ai_finished
                    mark_full_ai_finished(
                        session_id,
                        stop_reason=f"BeRoot failed: {exc}",
                    )
                except Exception:
                    pass
            return

        _emit_tool_progress(session_id, "BeRoot", "Scan finished — processing and attaching findings…")
        # Persist the enriched/sanitized text locally (do NOT re-download /tmp/beroot.txt
        # afterwards — that file lacks the sudo -l enrichment we append in-process).
        ensure_runtime_dirs()
        local_filename = str(BEROOT_DOWNLOADS_DIR / f"{session_id}_beroot.txt")
        beroot_for_ai = sanitize_beroot_for_prompt(beroot_string)
        try:
            Path(local_filename).write_text(beroot_for_ai, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            slog.warning(f"beroot: could not write local copy: {exc}")

        beroots[session_id] = local_filename
        priv_esc = prompts.get(session_id)
        if priv_esc is not None:
            priv_esc.clear_scanner_findings()
            priv_esc.set_BeRoot(beroot_for_ai, persist=True)

        _emit_tool_progress(session_id, "BeRoot", "Findings attached to session prompt.")
        preview = beroot_for_ai if len(beroot_for_ai) < 12000 else (
            beroot_for_ai[:6000] + "\n…[truncated]…\n" + beroot_for_ai[-4000:]
        )
        emit_session(session_id, f"[BeRoot] Scan complete ({len(beroot_string)} chars):\n{preview}", color="#1E90FF")
        slog.event(
            "BEROOT_OK",
            f"Scan complete ({len(beroot_string)} chars)",
            local_file=local_filename,
            with_ai=with_ai,
            duration_seconds=beroot_duration,
        )
        debug_logger.info(f"beroot.ok session_id={session_id!r} chars={len(beroot_string)} with_ai={with_ai}")
        _record_benchmark_scan_result(session_data, ok=True)
        _handoff_scanner_to_full_ai(session_data, source="beroot", tool_label="BeRoot", slog=slog)


def execute_linenum(session_data):
    """
    Background task: upload LinEnum to the target, run it, attach findings to the
    session prompt, then optionally hand off to Full AI (when with_ai=True).
    """
    with app.app_context():
        session_id = session_data["sid"]
        with_ai = bool(session_data.get("with_ai", True))
        slog = get_session_logger(session_id)
        ssh_conn = ssh_ssh_conns.get(session_id)

        if ssh_conn is None:
            emit_session(session_id, "[LinEnum] No SSH connection — connect first.", color="#f85149")
            loop[session_id] = 0
            _record_benchmark_scan_result(
                session_data,
                ok=False,
                error="LinEnum failed: no SSH connection",
            )
            if with_ai:
                try:
                    from ramigpt.benchmark.orchestrator import mark_full_ai_finished

                    mark_full_ai_finished(
                        session_id,
                        stop_reason="LinEnum failed: no SSH connection",
                    )
                except Exception:
                    pass
            return

        password = session_data.get("password") or ""
        slog.event(
            "LINENUM_START",
            "Uploading and running LinEnum on remote host",
            server=session_data.get("server"),
            port=session_data.get("port"),
            username=session_data.get("username"),
            with_ai=with_ai,
        )
        emit_session(
            session_id,
            f"[LinEnum] Uploading LinEnum.sh to /tmp … (AI={'on' if with_ai else 'off'})",
            color="#58a6ff",
        )
        _emit_tool_progress(session_id, "LinEnum", "Sending LinEnum.sh to remote host…")
        _emit_tool_progress(
            session_id,
            "LinEnum",
            "Executing scan on target — waiting for results (this may take several minutes)…",
        )
        debug_logger.info(
            f"linenum.start session_id={session_id!r} "
            f"host={session_data.get('server')!r}:{session_data.get('port')} with_ai={with_ai}"
        )

        try:
            linenum_started = time.monotonic()
            linenum_string = _run_linenum_on_remote(
                ssh_conn,
                password=password,
                slog=slog,
                timeout=300,
            )
            linenum_duration = round(time.monotonic() - linenum_started, 3)
        except Exception as exc:  # noqa: BLE001
            debug_logger.exception(f"linenum.failed session_id={session_id!r}")
            slog.exception(f"linenum failed: {exc}")
            slog.event("LINENUM_FAILED", str(exc))
            emit_session(session_id, f"[LinEnum] Failed: {exc}", color="#f85149")
            loop[session_id] = 0
            _record_benchmark_scan_result(
                session_data,
                ok=False,
                error=f"LinEnum failed: {exc}",
            )
            if with_ai:
                try:
                    from ramigpt.benchmark.orchestrator import mark_full_ai_finished

                    mark_full_ai_finished(
                        session_id,
                        stop_reason=f"LinEnum failed: {exc}",
                    )
                except Exception:
                    pass
            return

        _emit_tool_progress(session_id, "LinEnum", "Scan finished — processing and attaching findings…")
        ensure_runtime_dirs()
        local_filename = str(LINENUM_DOWNLOADS_DIR / f"{session_id}_linenum.txt")
        linenum_for_ai = sanitize_linenum_for_prompt(linenum_string)
        try:
            Path(local_filename).write_text(linenum_for_ai, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            slog.warning(f"linenum: could not write local copy: {exc}")

        linenums[session_id] = local_filename
        priv_esc = prompts.get(session_id)
        if priv_esc is not None:
            priv_esc.clear_scanner_findings()
            priv_esc.set_LinEnum(linenum_for_ai, persist=True)

        _emit_tool_progress(session_id, "LinEnum", "Findings attached to session prompt.")
        preview = linenum_for_ai if len(linenum_for_ai) < 12000 else (
            linenum_for_ai[:6000] + "\n…[truncated]…\n" + linenum_for_ai[-4000:]
        )
        emit_session(
            session_id,
            f"[LinEnum] Scan complete ({len(linenum_string)} chars):\n{preview}",
            color="#1E90FF",
        )
        slog.event(
            "LINENUM_OK",
            f"Scan complete ({len(linenum_string)} chars)",
            local_file=local_filename,
            with_ai=with_ai,
            duration_seconds=linenum_duration,
        )
        debug_logger.info(
            f"linenum.ok session_id={session_id!r} chars={len(linenum_string)} with_ai={with_ai}"
        )
        _record_benchmark_scan_result(session_data, ok=True)
        _handoff_scanner_to_full_ai(session_data, source="linenum", tool_label="LinEnum", slog=slog)


def execute_linpeas(session_data):
    """
    Background task: upload LinPEAS to the target, run it, attach findings to the
    session prompt, then optionally hand off to Full AI (when with_ai=True).
    """
    with app.app_context():
        session_id = session_data["sid"]
        with_ai = bool(session_data.get("with_ai", True))
        slog = get_session_logger(session_id)
        ssh_conn = ssh_ssh_conns.get(session_id)

        if ssh_conn is None:
            emit_session(session_id, "[LinPEAS] No SSH connection — connect first.", color="#f85149")
            loop[session_id] = 0
            _record_benchmark_scan_result(
                session_data,
                ok=False,
                error="LinPEAS failed: no SSH connection",
            )
            if with_ai:
                try:
                    from ramigpt.benchmark.orchestrator import mark_full_ai_finished

                    mark_full_ai_finished(
                        session_id,
                        stop_reason="LinPEAS failed: no SSH connection",
                    )
                except Exception:
                    pass
            return

        password = session_data.get("password") or ""
        slog.event(
            "LINPEAS_START",
            "Uploading and running LinPEAS on remote host",
            server=session_data.get("server"),
            port=session_data.get("port"),
            username=session_data.get("username"),
            with_ai=with_ai,
        )
        emit_session(
            session_id,
            f"[LinPEAS] Uploading linpeas.sh to /tmp … (AI={'on' if with_ai else 'off'})",
            color="#58a6ff",
        )
        _emit_tool_progress(session_id, "LinPEAS", "Sending linpeas.sh to remote host…")
        _emit_tool_progress(
            session_id,
            "LinPEAS",
            "Executing scan on target — waiting for results (this may take several minutes)…",
        )
        debug_logger.info(
            f"linpeas.start session_id={session_id!r} "
            f"host={session_data.get('server')!r}:{session_data.get('port')} with_ai={with_ai}"
        )

        try:
            linpeas_started = time.monotonic()
            linpeas_string = _run_linpeas_on_remote(
                ssh_conn,
                password=password,
                slog=slog,
                timeout=600,
            )
            linpeas_duration = round(time.monotonic() - linpeas_started, 3)
        except Exception as exc:  # noqa: BLE001
            debug_logger.exception(f"linpeas.failed session_id={session_id!r}")
            slog.exception(f"linpeas failed: {exc}")
            slog.event("LINPEAS_FAILED", str(exc))
            emit_session(session_id, f"[LinPEAS] Failed: {exc}", color="#f85149")
            loop[session_id] = 0
            _record_benchmark_scan_result(
                session_data,
                ok=False,
                error=f"LinPEAS failed: {exc}",
            )
            if with_ai:
                try:
                    from ramigpt.benchmark.orchestrator import mark_full_ai_finished

                    mark_full_ai_finished(
                        session_id,
                        stop_reason=f"LinPEAS failed: {exc}",
                    )
                except Exception:
                    pass
            return

        _emit_tool_progress(session_id, "LinPEAS", "Scan finished — processing and attaching findings…")
        ensure_runtime_dirs()
        local_filename = str(LINPEAS_DOWNLOADS_DIR / f"{session_id}_linpeas.txt")
        linpeas_for_ai = sanitize_linpeas_for_prompt(linpeas_string)
        try:
            Path(local_filename).write_text(linpeas_string, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            slog.warning(f"linpeas: could not write local copy: {exc}")

        linpeas_reports[session_id] = local_filename
        priv_esc = prompts.get(session_id)
        if priv_esc is not None:
            priv_esc.clear_scanner_findings()
            priv_esc.set_LinPEAS(linpeas_for_ai, persist=True)

        _emit_tool_progress(session_id, "LinPEAS", "Findings attached to session prompt.")
        preview = linpeas_for_ai if len(linpeas_for_ai) < 12000 else (
            linpeas_for_ai[:6000] + "\n…[truncated]…\n" + linpeas_for_ai[-4000:]
        )
        emit_session(
            session_id,
            f"[LinPEAS] Scan complete ({len(linpeas_string)} chars):\n{preview}",
            color="#1E90FF",
        )
        slog.event(
            "LINPEAS_OK",
            f"Scan complete ({len(linpeas_string)} chars)",
            local_file=local_filename,
            with_ai=with_ai,
            duration_seconds=linpeas_duration,
        )
        debug_logger.info(
            f"linpeas.ok session_id={session_id!r} chars={len(linpeas_string)} with_ai={with_ai}"
        )
        _record_benchmark_scan_result(session_data, ok=True)
        _handoff_scanner_to_full_ai(session_data, source="linpeas", tool_label="LinPEAS", slog=slog)
