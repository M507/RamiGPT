"""Persist completed benchmark runs under data/benchmark/results/ for analysis."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ramigpt.paths import BENCHMARK_RESULTS_DIR, ensure_runtime_dirs
from ramigpt.utils import debug_logger


def _utcnow_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", (value or "").strip())
    return cleaned or "run"


def _read_events(events_path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not events_path.is_file():
        return rows
    try:
        with events_path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return rows


def _latest_events_path(suite_dir: Path, target_id: str) -> Optional[Path]:
    target_root = suite_dir / _safe_name(target_id)
    if not target_root.is_dir():
        return None
    candidates = sorted(
        p for p in target_root.glob("*/events.jsonl") if p.is_file()
    )
    return candidates[-1] if candidates else None


def enrich_target_from_events(item: Dict[str, Any], suite_dir: Optional[str]) -> Dict[str, Any]:
    """Fill ai_requests / tools_used from events.jsonl when missing."""
    out = dict(item)
    if not suite_dir:
        return out
    events_path = _latest_events_path(Path(suite_dir), out.get("target_id") or "")
    if events_path is None:
        return out
    out.setdefault("events_path", str(events_path))
    events = _read_events(events_path)
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
    return out


def build_result_document(run_public: Dict[str, Any], *, settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Normalize a finished BenchmarkRun public dict into an analysis document."""
    settings = settings or {}
    suite_dir = run_public.get("log_dir") or run_public.get("suite_dir")
    targets = [
        enrich_target_from_events(t, suite_dir) for t in (run_public.get("targets") or [])
    ]
    counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0, "other": 0}
    for t in targets:
        st = (t.get("status") or "other").lower()
        if st in counts:
            counts[st] += 1
        else:
            counts["other"] += 1

    suite_provider = settings.get("provider") or ""
    suite_model = settings.get("model") or ""
    for t in targets:
        suite_provider = suite_provider or (t.get("provider") or "")
        suite_model = suite_model or (t.get("model") or "")

    elapsed_total = 0.0
    for t in targets:
        try:
            elapsed_total += float(t.get("elapsed_seconds") or 0)
        except (TypeError, ValueError):
            pass

    doc = {
        "schema_version": 1,
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
        "tools_configured": run_public.get("tools") or {},
        "targets": targets,
        "summary": {
            **counts,
            "target_count": len(targets),
            "elapsed_seconds_total": round(elapsed_total, 3),
            "commands_total": sum(
                int(
                    t["commands_count"]
                    if t.get("commands_count") is not None
                    else t["ai_requests"]
                )
                for t in targets
                if t.get("commands_count") is not None or t.get("ai_requests") is not None
            ),
            "ai_requests_total": sum(
                int(t["ai_requests"])
                for t in targets
                if t.get("ai_requests") is not None
            ),
            "prompt_tokens_total": sum(
                int(t["prompt_tokens"])
                for t in targets
                if t.get("prompt_tokens") is not None
            ),
            "completion_tokens_total": sum(
                int(t["completion_tokens"])
                for t in targets
                if t.get("completion_tokens") is not None
            ),
            "tokens_total": sum(
                int(t["tokens_total"])
                for t in targets
                if t.get("tokens_total") is not None
            ),
            "tools_used_any": sorted(
                {tool for t in targets for tool in (t.get("tools_used") or [])}
            ),
        },
        "suite_log_dir": suite_dir,
        "result_dir": None,
    }
    return doc


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
    summary_lines = [
        f"Benchmark result {doc.get('id')}",
        f"phase={doc.get('phase')} mode={doc.get('mode')} host={doc.get('host')}",
        f"model={doc.get('provider')}/{doc.get('model')}",
        f"started={doc.get('started_at')} finished={doc.get('finished_at')}",
        f"repetition={doc.get('repetition')}/{doc.get('repetitions')}",
        f"tools_configured={json.dumps(doc.get('tools_configured') or {})}",
        f"summary={json.dumps(doc.get('summary') or {})}",
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
        for cmd in t.get("commands") or []:
            summary_lines.append(f"      $ {cmd}")
    (result_dir / "summary.txt").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    index_path = BENCHMARK_RESULTS_DIR / "index.jsonl"
    index_row = {
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

    debug_logger.info(f"[benchmark] results written → {result_path}")
    return result_path


def write_batch_summary(
    batch_dir: Path,
    *,
    batch_id: str,
    runs: List[Dict[str, Any]],
) -> Path:
    batch_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "batch_id": batch_id,
        "repetitions": len(runs),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "runs": [
            {
                "id": r.get("id"),
                "repetition": r.get("repetition"),
                "phase": r.get("phase"),
                "result_dir": r.get("result_dir"),
                "summary": r.get("summary"),
                "provider": r.get("provider"),
                "model": r.get("model"),
            }
            for r in runs
        ],
    }
    path = batch_dir / "batch.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    return path
