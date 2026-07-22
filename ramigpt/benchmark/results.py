"""Persist completed benchmark runs under data/benchmark/results/ for analysis."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ramigpt.benchmark.profile import collaborative_profile_key, profile_display_label
from ramigpt.benchmark.tools import enabled_tool_ids, normalize_tools
from ramigpt.paths import BENCHMARK_RESULTS_DIR, ensure_runtime_dirs
from ramigpt.utils import debug_logger

# Detailed timing breakdown (beroot / ai_turn / shell_io) — sole result format.
BENCHMARK_RESULT_SCHEMA_VERSION = 2

# Infra/setup failures (network, deploy, etc.) — excluded from pass rate and timing averages.
INFRA_EXCLUDED_TARGET_STATUSES = frozenset({"error", "skipped"})

_LOG_PREFIX = "[benchmark-results]"


def normalize_target_status(status: Any) -> str:
    st = (str(status or "other")).strip().lower()
    if st in {"passed", "failed", "error", "skipped"}:
        return st
    return "other"


def is_benchmark_attempt(status: Any) -> bool:
    """True when the target actually ran (not infra error / skipped)."""
    return normalize_target_status(status) not in INFRA_EXCLUDED_TARGET_STATUSES


def build_run_summary(targets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate per-run summary; infra errors/skips do not affect pass rate or timing totals."""
    counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0, "other": 0}
    for target in targets:
        st = normalize_target_status(target.get("status"))
        if st in counts:
            counts[st] += 1
        else:
            counts["other"] += 1

    attempted_targets = [t for t in targets if is_benchmark_attempt(t.get("status"))]
    attempted = len(attempted_targets)

    elapsed_total = 0.0
    for target in attempted_targets:
        try:
            elapsed_total += float(target.get("elapsed_seconds") or 0)
        except (TypeError, ValueError):
            pass

    pass_rate = round(counts["passed"] / attempted, 4) if attempted else None

    return {
        **counts,
        "target_count": len(targets),
        "attempted": attempted,
        "pass_rate": pass_rate,
        "elapsed_seconds_total": round(elapsed_total, 3),
        "commands_total": sum(
            int(
                target["commands_count"]
                if target.get("commands_count") is not None
                else target["ai_requests"]
            )
            for target in attempted_targets
            if target.get("commands_count") is not None or target.get("ai_requests") is not None
        ),
        "ai_requests_total": sum(
            int(target["ai_requests"])
            for target in attempted_targets
            if target.get("ai_requests") is not None
        ),
        "prompt_tokens_total": sum(
            int(target["prompt_tokens"])
            for target in attempted_targets
            if target.get("prompt_tokens") is not None
        ),
        "completion_tokens_total": sum(
            int(target["completion_tokens"])
            for target in attempted_targets
            if target.get("completion_tokens") is not None
        ),
        "tokens_total": sum(
            int(target["tokens_total"])
            for target in attempted_targets
            if target.get("tokens_total") is not None
        ),
        "tools_used_any": sorted(
            {tool for target in attempted_targets for tool in (target.get("tools_used") or [])}
        ),
        "beroot_seconds_total": _sum_optional(
            [
                (target.get("timing_summary") or {}).get("beroot_seconds")
                for target in attempted_targets
            ]
        ),
        "ai_llm_seconds_total": _sum_optional(
            [
                (target.get("timing_summary") or {}).get("ai_llm_seconds")
                for target in attempted_targets
            ]
        ),
        "shell_seconds_total": _sum_optional(
            [
                (target.get("timing_summary") or {}).get("shell_seconds")
                for target in attempted_targets
            ]
        ),
        "other_seconds_total": _sum_optional(
            [
                (target.get("timing_summary") or {}).get("other_seconds")
                for target in attempted_targets
            ]
        ),
    }


def _log_info(message: str) -> None:
    debug_logger.info(f"{_LOG_PREFIX} {message}")


def _log_warning(message: str) -> None:
    debug_logger.warning(f"{_LOG_PREFIX} {message}")


def _log_error(message: str, *, exc: Optional[BaseException] = None) -> None:
    if exc is not None:
        debug_logger.exception(f"{_LOG_PREFIX} {message}")
    else:
        debug_logger.error(f"{_LOG_PREFIX} {message}")


def _empty_target_timing() -> Dict[str, Any]:
    return {
        "timeline": [],
        "tool_runs": [],
        "ai_turns": [],
        "shell_runs": [],
        "timing_summary": {},
    }


def clear_benchmark_results(*, results_dir: Optional[Path] = None) -> int:
    """Remove all persisted benchmark result folders and index files."""
    ensure_runtime_dirs()
    root = results_dir or BENCHMARK_RESULTS_DIR
    removed = 0
    if not root.is_dir():
        return 0
    for path in root.iterdir():
        if path.name == ".gitkeep":
            continue
        if path.is_dir():
            shutil.rmtree(path)
            removed += 1
        elif path.is_file():
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", (value or "").strip())
    return cleaned or "run"


def _utcnow_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_events(events_path: Path) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    stats: Dict[str, Any] = {
        "path": str(events_path),
        "lines_read": 0,
        "events_parsed": 0,
        "blank_lines": 0,
        "json_errors": 0,
        "read_error": None,
    }
    if not events_path.is_file():
        stats["read_error"] = "events file not found"
        return rows, stats
    try:
        with events_path.open("r", encoding="utf-8", errors="replace") as fh:
            for line_no, line in enumerate(fh, start=1):
                stats["lines_read"] = line_no
                stripped = line.strip()
                if not stripped:
                    stats["blank_lines"] += 1
                    continue
                try:
                    rows.append(json.loads(stripped))
                    stats["events_parsed"] += 1
                except json.JSONDecodeError as exc:
                    stats["json_errors"] += 1
                    _log_warning(
                        f"invalid JSON in {events_path}:{line_no}: {exc}"
                    )
    except OSError as exc:
        stats["read_error"] = str(exc)
        _log_error(f"failed to read events {events_path}: {exc}")
    return rows, stats


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    text = str(ts).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _seconds_between(start_ts: Optional[str], end_ts: Optional[str]) -> Optional[float]:
    start = _parse_ts(start_ts)
    end = _parse_ts(end_ts)
    if start is None or end is None:
        return None
    return round(max(0.0, (end - start).total_seconds()), 3)


def _float_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def _sum_optional(values: List[Optional[float]]) -> Optional[float]:
    nums = [v for v in values if v is not None]
    if not nums:
        return None
    return round(sum(nums), 3)


def _build_target_timing(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build a per-target timing breakdown from session events.

    Separates tool runs (BeRoot), AI LLM latency, shell execution, and overhead.
    """
    timeline: List[Dict[str, Any]] = []
    tool_runs: List[Dict[str, Any]] = []
    ai_turns: List[Dict[str, Any]] = []
    shell_runs: List[Dict[str, Any]] = []

    beroot_start_ts: Optional[str] = None
    linenum_start_ts: Optional[str] = None
    linpeas_start_ts: Optional[str] = None
    full_ai_start_ts: Optional[str] = None
    last_event_ts: Optional[str] = None
    pending_ai: Optional[Dict[str, Any]] = None

    def _append_timeline(entry: Dict[str, Any]) -> None:
        timeline.append(entry)
        nonlocal last_event_ts
        if entry.get("finished_at"):
            last_event_ts = entry.get("finished_at")
        elif entry.get("ts"):
            last_event_ts = entry.get("ts")

    for ev in events:
        kind = (ev.get("kind") or "").upper()
        ts = ev.get("ts")
        details = ev.get("details") or {}

        if kind == "BEROOT_START":
            beroot_start_ts = ts or beroot_start_ts
            _append_timeline(
                {
                    "phase": "beroot_start",
                    "type": "phase",
                    "ts": ts,
                }
            )
            continue

        if kind == "BEROOT_OK":
            duration = _float_or_none(details.get("duration_seconds"))
            if duration is None:
                duration = _seconds_between(beroot_start_ts, ts)
            tool = {
                "tool": "beroot",
                "started_at": beroot_start_ts,
                "finished_at": ts,
                "duration_seconds": duration,
                "with_ai": details.get("with_ai"),
            }
            tool_runs.append(tool)
            _append_timeline({"phase": "beroot", "type": "tool", **tool})
            continue

        if kind in {"BEROOT_FAILED"}:
            duration = _seconds_between(beroot_start_ts, ts)
            tool = {
                "tool": "beroot",
                "started_at": beroot_start_ts,
                "finished_at": ts,
                "duration_seconds": duration,
                "status": "failed",
            }
            tool_runs.append(tool)
            _append_timeline({"phase": "beroot_failed", "type": "tool", **tool})
            continue

        if kind == "LINENUM_START":
            linenum_start_ts = ts or linenum_start_ts
            _append_timeline(
                {
                    "phase": "linenum_start",
                    "type": "phase",
                    "ts": ts,
                }
            )
            continue

        if kind == "LINENUM_OK":
            duration = _float_or_none(details.get("duration_seconds"))
            if duration is None:
                duration = _seconds_between(linenum_start_ts, ts)
            tool = {
                "tool": "linenum",
                "started_at": linenum_start_ts,
                "finished_at": ts,
                "duration_seconds": duration,
                "with_ai": details.get("with_ai"),
            }
            tool_runs.append(tool)
            _append_timeline({"phase": "linenum", "type": "tool", **tool})
            continue

        if kind in {"LINENUM_FAILED"}:
            duration = _seconds_between(linenum_start_ts, ts)
            tool = {
                "tool": "linenum",
                "started_at": linenum_start_ts,
                "finished_at": ts,
                "duration_seconds": duration,
                "status": "failed",
            }
            tool_runs.append(tool)
            _append_timeline({"phase": "linenum_failed", "type": "tool", **tool})
            continue

        if kind == "LINPEAS_START":
            linpeas_start_ts = ts or linpeas_start_ts
            _append_timeline(
                {
                    "phase": "linpeas_start",
                    "type": "phase",
                    "ts": ts,
                }
            )
            continue

        if kind == "LINPEAS_OK":
            duration = _float_or_none(details.get("duration_seconds"))
            if duration is None:
                duration = _seconds_between(linpeas_start_ts, ts)
            tool = {
                "tool": "linpeas",
                "started_at": linpeas_start_ts,
                "finished_at": ts,
                "duration_seconds": duration,
                "with_ai": details.get("with_ai"),
            }
            tool_runs.append(tool)
            _append_timeline({"phase": "linpeas", "type": "tool", **tool})
            continue

        if kind in {"LINPEAS_FAILED"}:
            duration = _seconds_between(linpeas_start_ts, ts)
            tool = {
                "tool": "linpeas",
                "started_at": linpeas_start_ts,
                "finished_at": ts,
                "duration_seconds": duration,
                "status": "failed",
            }
            tool_runs.append(tool)
            _append_timeline({"phase": "linpeas_failed", "type": "tool", **tool})
            continue

        if kind in {"FULL_AI_START", "FULL_AI_REQUESTED"}:
            if kind == "FULL_AI_START":
                full_ai_start_ts = ts or full_ai_start_ts
            _append_timeline(
                {
                    "phase": kind.lower(),
                    "type": "phase",
                    "ts": ts,
                    "provider": details.get("provider"),
                    "model": details.get("model"),
                }
            )
            continue

        if kind == "AI_TURN":
            req = details.get("request_n")
            if req is None:
                req = len(ai_turns) + 1
            llm_duration = _float_or_none(details.get("duration_seconds"))
            if llm_duration is None:
                llm_duration = _seconds_between(last_event_ts, ts)
            turn = {
                "request": int(req),
                "ts": ts,
                "started_at": last_event_ts,
                "finished_at": ts,
                "llm_duration_seconds": llm_duration,
                "shell_duration_seconds": None,
                "command": details.get("filtered_command") or details.get("command") or "",
                "provider": details.get("provider"),
                "model": details.get("model"),
                "prompt_tokens": details.get("prompt_tokens"),
                "completion_tokens": details.get("completion_tokens"),
                "total_tokens": details.get("total_tokens"),
            }
            ai_turns.append(turn)
            pending_ai = turn
            _append_timeline(
                {
                    "phase": "ai_turn",
                    "type": "ai",
                    "request": turn["request"],
                    "ts": ts,
                    "duration_seconds": llm_duration,
                    "total_tokens": turn.get("total_tokens"),
                    "command": turn.get("command"),
                }
            )
            continue

        if kind == "SHELL_IO":
            req = details.get("request_n")
            shell_duration = _float_or_none(details.get("duration_seconds"))
            if shell_duration is None and pending_ai is not None:
                shell_duration = _seconds_between(pending_ai.get("ts"), ts)
            shell = {
                "request": req,
                "ts": ts,
                "started_at": pending_ai.get("ts") if pending_ai else last_event_ts,
                "finished_at": ts,
                "duration_seconds": shell_duration,
                "command": details.get("command") or "",
                "note": details.get("note") or "",
            }
            shell_runs.append(shell)
            if pending_ai is not None and (
                req is None or req == pending_ai.get("request")
            ):
                pending_ai["shell_duration_seconds"] = shell_duration
                pending_ai = None
            _append_timeline(
                {
                    "phase": "shell_io",
                    "type": "shell",
                    "request": shell.get("request"),
                    "ts": ts,
                    "duration_seconds": shell_duration,
                    "command": shell.get("command"),
                }
            )
            continue

        if kind == "FULL_AI_END":
            duration = _seconds_between(full_ai_start_ts, ts)
            _append_timeline(
                {
                    "phase": "full_ai_end",
                    "type": "phase",
                    "ts": ts,
                    "duration_seconds": duration,
                    "requests_run": details.get("requests_run"),
                    "got_root": details.get("got_root"),
                    "stop_reason": details.get("stop_reason"),
                }
            )
            continue

    beroot_seconds = _sum_optional(
        [t.get("duration_seconds") for t in tool_runs if t.get("tool") == "beroot"]
    )
    ai_llm_seconds = _sum_optional([t.get("llm_duration_seconds") for t in ai_turns])
    shell_seconds = _sum_optional([s.get("duration_seconds") for s in shell_runs])

    full_ai_phase = next(
        (e for e in reversed(timeline) if e.get("phase") == "full_ai_end"),
        None,
    )
    full_ai_seconds = (
        full_ai_phase.get("duration_seconds") if full_ai_phase else None
    )
    if full_ai_seconds is None and (ai_llm_seconds is not None or shell_seconds is not None):
        full_ai_seconds = _sum_optional([ai_llm_seconds, shell_seconds])

    measured = _sum_optional(
        [beroot_seconds, ai_llm_seconds, shell_seconds]
    )

    return {
        "timeline": timeline,
        "tool_runs": tool_runs,
        "ai_turns": ai_turns,
        "shell_runs": shell_runs,
        "timing_summary": {
            "beroot_seconds": beroot_seconds,
            "ai_llm_seconds": ai_llm_seconds,
            "shell_seconds": shell_seconds,
            "full_ai_seconds": full_ai_seconds,
            "measured_seconds": measured,
        },
    }


def _format_timing_line(label: str, seconds: Optional[float]) -> str:
    if seconds is None:
        return f"{label}=—"
    return f"{label}={seconds}s"


def _format_target_timing_summary(target: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    timing = target.get("timing_summary") or {}
    total = target.get("elapsed_seconds")
    measured = timing.get("measured_seconds")
    overhead = None
    if total is not None and measured is not None:
        overhead = round(max(0.0, float(total) - float(measured)), 3)

    lines.append(
        "      timing: "
        + " | ".join(
            [
                _format_timing_line("total", _float_or_none(total)),
                _format_timing_line("beroot", timing.get("beroot_seconds")),
                _format_timing_line("ai_llm", timing.get("ai_llm_seconds")),
                _format_timing_line("shell", timing.get("shell_seconds")),
                _format_timing_line("full_ai", timing.get("full_ai_seconds")),
                _format_timing_line("other", overhead),
            ]
        )
    )

    for tool in target.get("tool_runs") or []:
        lines.append(
            f"      tool {tool.get('tool')}: "
            f"{_format_timing_line('duration', tool.get('duration_seconds'))} "
            f"({tool.get('started_at') or '?'} → {tool.get('finished_at') or '?'})"
        )

    for turn in target.get("ai_turns") or []:
        tokens = turn.get("total_tokens")
        token_txt = (
            f"tokens={tokens} (prompt={turn.get('prompt_tokens')}, completion={turn.get('completion_tokens')})"
            if tokens is not None
            else "tokens=—"
        )
        lines.append(
            f"      ai #{turn.get('request')}: "
            f"{_format_timing_line('llm', turn.get('llm_duration_seconds'))} "
            f"{_format_timing_line('shell', turn.get('shell_duration_seconds'))} "
            f"{token_txt} "
            f"$ {turn.get('command') or ''}"
        )

    for shell in target.get("shell_runs") or []:
        if any(
            (turn.get("shell_duration_seconds") is not None)
            and turn.get("request") == shell.get("request")
            for turn in (target.get("ai_turns") or [])
        ):
            continue
        lines.append(
            f"      shell #{shell.get('request') or '?'}: "
            f"{_format_timing_line('duration', shell.get('duration_seconds'))} "
            f"$ {shell.get('command') or ''}"
        )

    return lines


def _diagnose_target(
    target: Dict[str, Any],
    *,
    events: List[Dict[str, Any]],
    event_stats: Optional[Dict[str, Any]] = None,
    tools_configured: Optional[Dict[str, bool]] = None,
) -> List[str]:
    """Return human-readable issues that may explain incomplete result data."""
    issues: List[str] = []
    target_id = target.get("target_id") or "?"
    status = (target.get("status") or "").lower()
    prefix = f"target={target_id}"

    if event_stats:
        if event_stats.get("read_error"):
            issues.append(f"{prefix}: events unreadable — {event_stats['read_error']}")
        if int(event_stats.get("json_errors") or 0) > 0:
            issues.append(
                f"{prefix}: {event_stats['json_errors']} malformed event line(s) in "
                f"{event_stats.get('path')}"
            )
        if not events and not event_stats.get("read_error"):
            issues.append(f"{prefix}: events file empty — {event_stats.get('path')}")

    kinds = {(ev.get("kind") or "").upper() for ev in events}
    ai_turns = list(target.get("ai_turns") or [])
    tool_runs = list(target.get("tool_runs") or [])
    timing = target.get("timing_summary") or {}

    if tools_configured and tools_configured.get("beroot"):
        if "BEROOT_START" in kinds and "BEROOT_OK" not in kinds and "BEROOT_FAILED" not in kinds:
            issues.append(f"{prefix}: BeRoot started but no BEROOT_OK/BEROOT_FAILED event")
        if "beroot" in (target.get("tools_used") or []) and not any(
            t.get("tool") == "beroot" for t in tool_runs
        ):
            issues.append(f"{prefix}: BeRoot listed in tools_used but no tool_runs timing")

    if tools_configured and tools_configured.get("linenum"):
        if "LINENUM_START" in kinds and "LINENUM_OK" not in kinds and "LINENUM_FAILED" not in kinds:
            issues.append(f"{prefix}: LinEnum started but no LINENUM_OK/LINENUM_FAILED event")
        if "linenum" in (target.get("tools_used") or []) and not any(
            t.get("tool") == "linenum" for t in tool_runs
        ):
            issues.append(f"{prefix}: LinEnum listed in tools_used but no tool_runs timing")

    if tools_configured and tools_configured.get("linpeas"):
        if "LINPEAS_START" in kinds and "LINPEAS_OK" not in kinds and "LINPEAS_FAILED" not in kinds:
            issues.append(f"{prefix}: LinPEAS started but no LINPEAS_OK/LINPEAS_FAILED event")
        if "linpeas" in (target.get("tools_used") or []) and not any(
            t.get("tool") == "linpeas" for t in tool_runs
        ):
            issues.append(f"{prefix}: LinPEAS listed in tools_used but no tool_runs timing")

    ai_requests = target.get("ai_requests")
    if ai_requests is not None and ai_turns and int(ai_requests) != len(ai_turns):
        issues.append(
            f"{prefix}: ai_requests={ai_requests} but captured {len(ai_turns)} AI_TURN event(s)"
        )

    if (
        status in {"passed", "failed"}
        and not ai_turns
        and not tool_runs
    ):
        issues.append(f"{prefix}: no AI/tool timing captured (status={status})")

    if ai_turns and "FULL_AI_END" not in kinds and status not in {"skipped", "pending"}:
        issues.append(f"{prefix}: AI turns logged but FULL_AI_END missing")

    for turn in ai_turns:
        req = turn.get("request")
        if turn.get("llm_duration_seconds") is None:
            issues.append(f"{prefix}: ai #{req} missing llm_duration_seconds (estimated from timestamps only)")
        if turn.get("command") and turn.get("shell_duration_seconds") is None:
            issues.append(f"{prefix}: ai #{req} missing shell_duration_seconds")
        if turn.get("total_tokens") is None:
            issues.append(f"{prefix}: ai #{req} missing token usage")

    total = _float_or_none(target.get("elapsed_seconds"))
    other = _float_or_none(timing.get("other_seconds"))
    measured = _float_or_none(timing.get("measured_seconds"))
    if total is not None and measured is not None and other is not None:
        if other > 30 or (total > 0 and other / total > 0.35):
            issues.append(
                f"{prefix}: large unaccounted time other={other}s "
                f"(total={total}s measured={measured}s) — check connect/deploy overhead"
            )

    if target.get("elapsed_seconds") is None and status not in {"pending", "running"}:
        issues.append(f"{prefix}: elapsed_seconds missing on target record")

    if not target.get("events_path"):
        issues.append(f"{prefix}: no events_path (suite logs missing or not linked)")

    return issues


def _write_results_log(result_dir: Path, lines: List[str]) -> None:
    if not lines:
        return
    path = result_dir / "results.log"
    body = "\n".join(lines) + "\n"
    path.write_text(body, encoding="utf-8")
    _log_warning(f"result issues written → {path} ({len(lines)} line(s))")


_BENCHMARK_EVENT_KINDS = frozenset(
    {
        "BENCHMARK_TARGET",
        "BEROOT_START",
        "BEROOT_OK",
        "BEROOT_FAILED",
        "BEROOT_FULL_AI",
        "LINENUM_START",
        "LINENUM_OK",
        "LINENUM_FAILED",
        "LINPEAS_START",
        "LINPEAS_OK",
        "LINPEAS_FAILED",
        "FULL_AI_START",
        "FULL_AI_END",
        "FULL_AI_REQUESTED",
        "AI_TURN",
        "SHELL_IO",
    }
)


def _events_path_from_runs_index(target_root: Path) -> Optional[Path]:
    """Return the benchmark run's events file recorded in runs.index."""
    index_path = target_root / "runs.index"
    if not index_path.is_file():
        return None
    try:
        lines = index_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (entry.get("reason") or "").lower() != "benchmark":
            continue
        run_name = str(entry.get("run") or "").strip()
        if not run_name:
            continue
        path = target_root / run_name / "events.jsonl"
        if path.is_file():
            return path
    return None


def _score_events_path(path: Path) -> tuple[int, int]:
    """Prefer logs that contain benchmark/AI activity over adhoc reconnect noise."""
    events, stats = _read_events(path)
    kinds = {(ev.get("kind") or "").upper() for ev in events}
    return (len(kinds & _BENCHMARK_EVENT_KINDS), int(stats.get("events_parsed") or 0))


def _best_events_path(suite_dir: Path, target_id: str) -> Optional[Path]:
    """
    Pick the events.jsonl that belongs to the benchmark target run.

    Lexicographic "latest" is wrong: timeout teardown often creates 002_* adhoc
    or reconnect runs after 001_*_benchmark, hiding BeRoot/AI timing in results.
    """
    target_root = suite_dir / _safe_name(target_id)
    if not target_root.is_dir():
        return None
    candidates = [p for p in target_root.glob("*/events.jsonl") if p.is_file()]
    if not candidates:
        return None

    from_index = _events_path_from_runs_index(target_root)
    if from_index is not None:
        return from_index

    benchmark_candidates = [
        p for p in candidates if p.parent.name.endswith("_benchmark")
    ]
    if benchmark_candidates:
        return max(benchmark_candidates, key=_score_events_path)

    return max(candidates, key=_score_events_path)


def enrich_target_from_events(
    item: Dict[str, Any],
    suite_dir: Optional[str],
    *,
    tools_configured: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    """Build v2 target record with timing, tokens, and command details from events."""
    out = dict(item)
    target_id = out.get("target_id") or "?"
    if not suite_dir:
        out.update(_empty_target_timing())
        out["issues"] = [f"target={target_id}: no suite_dir on run record"]
        _log_warning(out["issues"][0])
        return out
    events_path = _best_events_path(Path(suite_dir), target_id)
    if events_path is None:
        out.update(_empty_target_timing())
        out["issues"] = [
            f"target={target_id}: no events.jsonl under {suite_dir}/{_safe_name(target_id)}/"
        ]
        _log_warning(out["issues"][0])
        return out
    out.setdefault("events_path", str(events_path))
    events, event_stats = _read_events(events_path)
    _log_info(
        f"target={target_id}: parsed {event_stats.get('events_parsed')} event(s) from {events_path}"
    )
    tools_used = list(out.get("tools_used") or [])
    ai_requests = out.get("ai_requests")
    provider = out.get("provider") or ""
    model = out.get("model") or ""
    got_root = out.get("got_root")
    commands: List[str] = list(out.get("commands") or [])
    ai_turn_count = 0
    prompt_tokens_total = 0
    completion_tokens_total = 0
    tokens_total = 0
    have_token_data = False
    started_ts = out.get("started_at")
    finished_ts = out.get("finished_at")
    for ev in events:
        kind = (ev.get("kind") or "").upper()
        details = ev.get("details") or {}
        ts = ev.get("ts")
        if kind in {"BEROOT_START", "BEROOT_OK", "BEROOT_FULL_AI"}:
            if "beroot" not in tools_used:
                tools_used.append("beroot")
        if kind in {"LINENUM_START", "LINENUM_OK", "LINENUM_FULL_AI"}:
            if "linenum" not in tools_used:
                tools_used.append("linenum")
        if kind in {"LINPEAS_START", "LINPEAS_OK", "LINPEAS_FULL_AI"}:
            if "linpeas" not in tools_used:
                tools_used.append("linpeas")
        if kind == "AI_TURN":
            ai_turn_count += 1
            cmd = details.get("filtered_command") or details.get("command") or ""
            if cmd and cmd not in commands:
                commands.append(str(cmd))
            provider = provider or str(details.get("provider") or "")
            model = model or str(details.get("model") or "")
            pt = details.get("prompt_tokens")
            ct = details.get("completion_tokens")
            tt = details.get("total_tokens")
            if pt is not None or ct is not None or tt is not None:
                have_token_data = True
                prompt_tokens_total += int(pt or 0)
                completion_tokens_total += int(ct or 0)
                tokens_total += int(tt) if tt is not None else int(pt or 0) + int(ct or 0)
        if kind == "SHELL_IO":
            cmd = details.get("command") or ""
            if cmd and cmd not in commands:
                commands.append(str(cmd))
        if kind == "FULL_AI_END":
            if ai_requests is None and details.get("requests_run") is not None:
                try:
                    ai_requests = int(details["requests_run"])
                except (TypeError, ValueError):
                    pass
            if got_root is None and "got_root" in details:
                got_root = bool(details.get("got_root"))
            provider = provider or str(details.get("provider") or "")
            model = model or str(details.get("model") or "")
            finished_ts = finished_ts or ts
        if kind in {"FULL_AI_START", "FULL_AI_REQUESTED"}:
            provider = provider or str(details.get("provider") or "")
            model = model or str(details.get("model") or "")
            started_ts = started_ts or ts
        if kind == "BEROOT_START":
            started_ts = started_ts or ts
        if kind == "LINENUM_START":
            started_ts = started_ts or ts
        if kind == "LINPEAS_START":
            started_ts = started_ts or ts
    if ai_requests is None and ai_turn_count:
        ai_requests = ai_turn_count
    out["tools_used"] = tools_used
    out["ai_requests"] = ai_requests
    out["commands"] = commands
    out["commands_count"] = len(commands) if commands else ai_requests
    out["provider"] = provider
    out["model"] = model
    if have_token_data:
        out["prompt_tokens"] = prompt_tokens_total
        out["completion_tokens"] = completion_tokens_total
        out["tokens_total"] = tokens_total
    else:
        out.setdefault("prompt_tokens", out.get("prompt_tokens"))
        out.setdefault("completion_tokens", out.get("completion_tokens"))
        out.setdefault("tokens_total", out.get("tokens_total"))
    if started_ts:
        out["started_at"] = out.get("started_at") or started_ts
    if finished_ts:
        out["finished_at"] = out.get("finished_at") or finished_ts
    if got_root is not None:
        out["got_root"] = got_root

    timing = _build_target_timing(events)
    out.update(timing)
    total_elapsed = _float_or_none(out.get("elapsed_seconds"))
    measured = timing["timing_summary"].get("measured_seconds")
    if total_elapsed is not None and measured is not None:
        timing["timing_summary"]["other_seconds"] = round(
            max(0.0, total_elapsed - measured), 3
        )
        timing["timing_summary"]["total_seconds"] = total_elapsed
    elif total_elapsed is not None:
        timing["timing_summary"]["total_seconds"] = total_elapsed
    out["timing_summary"] = timing["timing_summary"]
    out["event_stats"] = event_stats
    out["issues"] = _diagnose_target(
        out,
        events=events,
        event_stats=event_stats,
        tools_configured=tools_configured,
    )
    for issue in out["issues"]:
        _log_warning(issue)
    return out


def build_result_document(
    run_public: Dict[str, Any],
    *,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Normalize a finished BenchmarkRun public dict into an analysis document."""
    settings = settings or {}
    suite_dir = run_public.get("log_dir") or run_public.get("suite_dir")
    tools_configured = normalize_tools(run_public.get("tools"))
    run_tools = enabled_tool_ids(tools_configured)
    targets = [
        enrich_target_from_events(
            t,
            suite_dir,
            tools_configured=tools_configured,
        )
        for t in (run_public.get("targets") or [])
    ]
    all_issues: List[str] = []
    for t in targets:
        all_issues.extend(t.get("issues") or [])
    if run_public.get("error"):
        all_issues.insert(0, f"suite: run error — {run_public.get('error')}")
    if not suite_dir:
        all_issues.insert(0, "suite: log_dir missing — timing enrichment limited")
    suite_provider = settings.get("provider") or ""
    suite_model = settings.get("model") or ""
    suite_model_key_name = settings.get("model_key_name") or run_public.get("model_key_name") or ""
    for t in targets:
        suite_provider = suite_provider or (t.get("provider") or "")
        suite_model = suite_model or (t.get("model") or "")
        if not suite_model_key_name:
            suite_model_key_name = t.get("model_key_name") or ""
        t.setdefault("model_key_name", suite_model_key_name or "")
        t.setdefault("model", suite_model)
        t.setdefault("provider", suite_provider)

    doc = {
        "schema_version": BENCHMARK_RESULT_SCHEMA_VERSION,
        "id": run_public.get("id"),
        "batch_id": run_public.get("batch_id"),
        "repetition": run_public.get("repetition"),
        "repetitions": run_public.get("repetitions"),
        "mode": run_public.get("mode"),
        "host": run_public.get("host"),
        "timeout_seconds": run_public.get("timeout_seconds"),
        "phase": run_public.get("phase"),
        "error": run_public.get("error"),
        "started_at": run_public.get("started_at"),
        "finished_at": run_public.get("finished_at"),
        "provider": suite_provider,
        "model": suite_model,
        "model_key_name": suite_model_key_name,
        "profile_key": collaborative_profile_key(
            suite_model_key_name,
            suite_provider,
            suite_model,
            run_public.get("hardware") or settings.get("hardware") or {},
        ),
        "profile_label": profile_display_label(
            suite_model_key_name,
            run_public.get("hardware") or settings.get("hardware") or {},
            provider=suite_provider,
            model=suite_model,
        ),
        "model_registry": run_public.get("model_registry") or settings.get("model_registry") or {},
        "hardware": run_public.get("hardware") or settings.get("hardware") or {},
        "role_objective": run_public.get("role_objective") or "",
        "suite_profile_id": run_public.get("suite_profile_id") or "",
        "suite_profile_name": run_public.get("suite_profile_name") or "",
        "tools_configured": tools_configured,
        "tools": run_tools,
        "targets": targets,
        "summary": build_run_summary(targets),
        "suite_log_dir": suite_dir,
        "result_dir": None,
        "issues": all_issues,
    }
    if all_issues:
        _log_warning(
            f"run={run_public.get('id')} result build flagged {len(all_issues)} issue(s)"
        )
    else:
        _log_info(
            f"run={run_public.get('id')} result build OK "
            f"({len(targets)} target(s), schema v{BENCHMARK_RESULT_SCHEMA_VERSION})"
        )
    return doc


def refresh_result_document_summary(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Recompute summary fields from targets (e.g. after changing aggregation rules)."""
    updated = dict(doc)
    updated["summary"] = build_run_summary(list(doc.get("targets") or []))
    return updated


def _write_result_summary_txt(doc: Dict[str, Any], result_dir: Path) -> None:
    summary_lines = [
        f"Benchmark result {doc.get('id')}",
        f"phase={doc.get('phase')} mode={doc.get('mode')} host={doc.get('host')}",
        f"model={doc.get('provider')}/{doc.get('model')}",
        f"model_key_name={doc.get('model_key_name') or '—'}",
        f"profile_label={doc.get('profile_label') or '—'}",
        f"hardware={json.dumps(doc.get('hardware') or {})}",
        f"started={doc.get('started_at')} finished={doc.get('finished_at')}",
        f"repetition={doc.get('repetition')}/{doc.get('repetitions')}",
        f"tools_configured={json.dumps(doc.get('tools_configured') or {})}",
        f"summary={json.dumps(doc.get('summary') or {})}",
        (
            "timing_totals: "
            f"beroot={((doc.get('summary') or {}).get('beroot_seconds_total'))}s "
            f"ai_llm={((doc.get('summary') or {}).get('ai_llm_seconds_total'))}s "
            f"shell={((doc.get('summary') or {}).get('shell_seconds_total'))}s "
            f"other={((doc.get('summary') or {}).get('other_seconds_total'))}s"
        ),
        "",
        "targets:",
    ]
    for t in doc.get("targets") or []:
        summary_lines.append(
            f"  - {t.get('target_id')}: {t.get('status')} "
            f"elapsed={t.get('elapsed_seconds')}s "
            f"commands={t.get('commands_count') if t.get('commands_count') is not None else t.get('ai_requests')} "
            f"ai_requests={t.get('ai_requests')} "
            f"tokens={t.get('tokens_total')} (prompt={t.get('prompt_tokens')}, completion={t.get('completion_tokens')}) "
            f"tools={t.get('tools_used')} "
            f"model={t.get('provider')}/{t.get('model')} "
            f"got_root={t.get('got_root')} "
            f"msg={t.get('message')}"
        )
        summary_lines.extend(_format_target_timing_summary(t))
        for issue in t.get("issues") or []:
            summary_lines.append(f"      ! {issue}")
    if doc.get("issues"):
        summary_lines.extend(["", "issues:"])
        summary_lines.extend(f"  - {line}" for line in doc["issues"])
    (result_dir / "summary.txt").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


def refresh_saved_result(path: Path) -> Path:
    """Refresh summary in a persisted result.json and its summary.txt."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc = refresh_result_document_summary(doc)
    path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    _write_result_summary_txt(doc, path.parent)
    return path


def refresh_all_saved_results(*, results_dir: Optional[Path] = None) -> int:
    """Recompute summaries for every result.json under the results tree."""
    root = results_dir or BENCHMARK_RESULTS_DIR
    count = 0
    for path in sorted(root.rglob("result.json")):
        if path.is_file():
            refresh_saved_result(path)
            count += 1
    return count


def write_benchmark_result(
    run_public: Dict[str, Any],
    *,
    settings: Optional[Dict[str, Any]] = None,
    batch_dir: Optional[Path] = None,
) -> Path:
    """
    Write one completed run under data/benchmark/results/.

    Layout:
      data/benchmark/results/
        index.jsonl
        latest.json
        <stamp>_<run8>/result.json
      or for multi-run batches:
        batch_<stamp>_<batch8>/
          batch.json
          run_01_<run8>/result.json
          run_02_...
    """
    ensure_runtime_dirs()
    BENCHMARK_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    doc = build_result_document(run_public, settings=settings)
    stamp = _utcnow_stamp()
    run_id = str(run_public.get("id") or "unknown")
    short = run_id[:8]
    rep = run_public.get("repetition")
    reps = run_public.get("repetitions") or 1
    issue_lines: List[str] = [
        f"Benchmark result log for run {run_id}",
        f"written_at={datetime.now(timezone.utc).isoformat()}",
        f"schema_version={BENCHMARK_RESULT_SCHEMA_VERSION}",
        f"result_phase={doc.get('phase')} host={doc.get('host')}",
        "",
    ]
    if doc.get("issues"):
        issue_lines.append(f"issues ({len(doc['issues'])}):")
        issue_lines.extend(f"  - {line}" for line in doc["issues"])
    else:
        issue_lines.append("issues: none")
    issue_lines.append("")

    if batch_dir is not None:
        batch_dir.mkdir(parents=True, exist_ok=True)
        folder_name = f"run_{int(rep or 1):02d}_{short}"
        result_dir = batch_dir / folder_name
    else:
        result_dir = BENCHMARK_RESULTS_DIR / f"{stamp}_{short}"

    result_dir.mkdir(parents=True, exist_ok=True)
    doc["result_dir"] = str(result_dir)
    result_path = result_dir / "result.json"
    result_path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    # Human-readable one-pager next to JSON.
    _write_result_summary_txt(doc, result_dir)
    _write_results_log(result_dir, issue_lines)

    index_path = BENCHMARK_RESULTS_DIR / "index.jsonl"
    index_row = {
        "schema_version": BENCHMARK_RESULT_SCHEMA_VERSION,
        "ts": datetime.now(timezone.utc).isoformat(),
        "id": doc.get("id"),
        "batch_id": doc.get("batch_id"),
        "repetition": doc.get("repetition"),
        "repetitions": doc.get("repetitions"),
        "phase": doc.get("phase"),
        "mode": doc.get("mode"),
        "host": doc.get("host"),
        "provider": doc.get("provider"),
        "model": doc.get("model"),
        "model_key_name": doc.get("model_key_name"),
        "role_objective": doc.get("role_objective"),
        "tools": doc.get("tools") or [],
        "summary": doc.get("summary"),
        "result_dir": str(result_dir),
        "result_json": str(result_path),
    }
    with index_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(index_row, ensure_ascii=False, default=str) + "\n")

    latest_path = BENCHMARK_RESULTS_DIR / "latest.json"
    latest_path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    _log_info(
        f"results written → {result_path} "
        f"(targets={len(doc.get('targets') or [])}, issues={len(doc.get('issues') or [])})"
    )
    try:
        from ramigpt.benchmark.master_results import update_master_results

        update_master_results()
    except Exception as exc:  # noqa: BLE001
        _log_error("failed to update master results", exc=exc)
    return result_path


def write_batch_summary(
    batch_dir: Path,
    *,
    batch_id: str,
    runs: List[Dict[str, Any]],
    model_plan: Optional[Dict[str, Any]] = None,
    role_plan: Optional[Dict[str, Any]] = None,
) -> Path:
    batch_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": BENCHMARK_RESULT_SCHEMA_VERSION,
        "batch_id": batch_id,
        "repetitions": len(runs),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "beroot_seconds_total": _sum_optional(
                [
                    (r.get("summary") or {}).get("beroot_seconds_total")
                    for r in runs
                ]
            ),
            "ai_llm_seconds_total": _sum_optional(
                [
                    (r.get("summary") or {}).get("ai_llm_seconds_total")
                    for r in runs
                ]
            ),
            "shell_seconds_total": _sum_optional(
                [
                    (r.get("summary") or {}).get("shell_seconds_total")
                    for r in runs
                ]
            ),
            "other_seconds_total": _sum_optional(
                [
                    (r.get("summary") or {}).get("other_seconds_total")
                    for r in runs
                ]
            ),
            "tokens_total": sum(
                int((r.get("summary") or {}).get("tokens_total") or 0) for r in runs
            ),
        },
        "runs": [
            {
                "id": r.get("id"),
                "repetition": r.get("repetition"),
                "phase": r.get("phase"),
                "result_dir": r.get("result_dir"),
                "summary": r.get("summary"),
                "provider": r.get("provider"),
                "model": r.get("model"),
                "model_key_name": r.get("model_key_name"),
                "role_objective": r.get("role_objective"),
                "tools": enabled_tool_ids(normalize_tools(r.get("tools"))),
            }
            for r in runs
        ],
    }
    if model_plan is not None:
        payload["model_plan"] = model_plan
    if role_plan is not None:
        payload["role_plan"] = role_plan
    path = batch_dir / "batch.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    try:
        from ramigpt.benchmark.master_results import update_master_results

        update_master_results()
    except Exception as exc:  # noqa: BLE001
        _log_error("failed to update master results after batch summary", exc=exc)
    return path
