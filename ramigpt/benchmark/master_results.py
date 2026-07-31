"""Collaborative master benchmark results — scan, calculate, merge, rank."""

from __future__ import annotations

import json
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ramigpt.benchmark.hardware import hardware_identity, hardware_key, hardware_label, normalize_stored_hardware
from ramigpt.benchmark.profile import (
    aggregate_model_key,
    collaborative_profile_key,
    parse_profile_key,
    profile_display_label,
)
from ramigpt.benchmark.results import is_benchmark_attempt, normalize_target_status
from ramigpt.benchmark.tools import enabled_tool_ids, normalize_tools
from ramigpt.paths import (
    BENCHMARK_MD_PATH,
    BENCHMARK_RESULTS_DIR,
    PROJECT_ROOT,
    README_PATH,
    ensure_runtime_dirs,
)
from ramigpt.utils import debug_logger

MASTER_RESULT_SCHEMA_VERSION = 2
MASTER_JSON_NAME = "master.json"
MASTER_SUMMARY_NAME = "master_summary.txt"

# Live collaborative stats live in README.md immediately after the project intro
# (first ``---`` under the title), under this heading. Merged run sheets update
# only the region between the start/end markers. README omits the long scenarios
# table; ``benchmark.md`` gets the full markdown (overall + profiles + scenarios).
README_BENCHMARK_HEADING = "## Collaborative benchmark results"
README_BENCHMARK_START = "<!-- benchmark-master:start -->"
README_BENCHMARK_END = "<!-- benchmark-master:end -->"
# Prose after the auto-spliced stats (end of the collaborative section).
README_BENCHMARK_SECTION_OUTRO = (
    "**Live stats only** — the tables above are rebuilt from real runs under "
    "[`data/benchmark/results/`](data/benchmark/results/) (per-run `result.json` "
    "sheets + [`master.json`](data/benchmark/results/master.json)). Commit updated "
    "sheets when you want to share results with the team (no automatic git actions).\n"
    "\n"
    "Per-scenario breakdown (profile · role · target · tools) and the same overall/"
    "profile tables also live in [`benchmark.md`](benchmark.md).\n"
    "\n"
    "**How collaborative merge works:** each run is a sheet under "
    "`data/benchmark/results/`. When the master is rebuilt, runs **merge into the "
    "same stats** when they share:\n"
    "\n"
    "- **Model `key_name`** — weights + modelfile params (registry under "
    "[`data/benchmark/models/`](data/benchmark/models/))\n"
    "- **Hardware lab profile** — `BENCHMARK_GPU_*` in `.env` (GPU name, VRAM MiB, "
    "driver, CUDA)\n"
    "- **Scenario** — role, target, and tools\n"
    "\n"
    "`BENCHMARK_GPU_POWER_LIMIT` is recorded on each run sheet but does **not** "
    "affect merge keys (same GPU lab profile merges even if watt cap differs).\n"
    "\n"
    "**What counts toward pass rate:** **root achieved**, **wall-clock timeouts**, "
    "and **request-budget exhaustion** (`max_requests`). Infra/provider aborts like "
    "`ai_provider_error`, tool upload failures, reconnect exhaustion, and other setup "
    "errors are recorded but excluded from pass rate and timing averages.\n"
    "\n"
    "The visible **profile** label is `key_name · GPU · VRAM · …`. Same profile + "
    "scenario → merged stats. Different model config or GPU lab → separate profile "
    "row.\n"
    "\n"
    "Sample file formats (not merged into the live master): "
    "[`data/benchmark/examples/`](data/benchmark/examples/).\n"
)
# Backward-compatible alias (older marker-creation call sites).
README_BENCHMARK_SECTION_INTRO = README_BENCHMARK_SECTION_OUTRO

README_PROJECT_LAYOUT_HEADING = "## Project layout"

# Same collaborative master content as README, plus scenarios. Markers keep the
# historical ``benchmark-scenarios`` name for splice stability.
BENCHMARK_MD_HEADING = "## Collaborative benchmark results"
BENCHMARK_MD_START = "<!-- benchmark-scenarios:start -->"
BENCHMARK_MD_END = "<!-- benchmark-scenarios:end -->"
# Backward-compatible aliases (older tests / callers).
BENCHMARK_SCENARIOS_HEADING = BENCHMARK_MD_HEADING
BENCHMARK_SCENARIOS_START = BENCHMARK_MD_START
BENCHMARK_SCENARIOS_END = BENCHMARK_MD_END
BENCHMARK_MD_SECTION_INTRO = (
    "Live collaborative stats from the same master as [`README.md`](README.md) "
    "(overall, profiles, and per-scenario tables). "
    "Full JSON: [`data/benchmark/results/master.json`](data/benchmark/results/master.json).\n"
)
BENCHMARK_SCENARIOS_SECTION_INTRO = BENCHMARK_MD_SECTION_INTRO
_LEGACY_BENCHMARK_MD_HEADING = "## Collaborative scenario results"

_LOG_PREFIX = "[benchmark-master]"


def _log_info(message: str) -> None:
    debug_logger.info(f"{_LOG_PREFIX} {message}")


def _log_warning(message: str) -> None:
    debug_logger.warning(f"{_LOG_PREFIX} {message}")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _float_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


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


def _model_key(provider: str, model: str) -> str:
    provider = (provider or "").strip()
    model = (model or "").strip()
    if provider and model:
        return f"{provider}/{model}"
    return model or provider or "unknown"


def _aggregate_model_key(model_key_name: str, provider: str, model: str) -> str:
    return aggregate_model_key(model_key_name, provider, model)


def _tools_key(tools: List[str]) -> str:
    if not tools:
        return "none"
    return ",".join(sorted(tools))


def _tools_from_doc(doc: Dict[str, Any]) -> List[str]:
    """Enabled tool ids configured at run start (extensible to multiple tools)."""
    configured = doc.get("tools_configured")
    if configured is None:
        configured = doc.get("tools")
    if configured is not None:
        return enabled_tool_ids(normalize_tools(configured))
    any_used = (doc.get("summary") or {}).get("tools_used_any")
    if isinstance(any_used, list):
        return sorted(str(tool).strip() for tool in any_used if str(tool).strip())
    return []


def _parse_scenario_key(scenario_key: str) -> Dict[str, Any]:
    model, hw_key, role, target_id, tools_key = (
        scenario_key.split("|", 4) + ["", "", "", ""]
    )[:5]
    tools = (
        [part for part in tools_key.split(",") if part]
        if tools_key and tools_key != "none"
        else []
    )
    return {
        "model": model,
        "hardware_key": hw_key or "unknown",
        "role": role,
        "target_id": target_id,
        "tools": tools,
    }


def _scenario_key(
    model_key_name: str,
    provider: str,
    model: str,
    role: str,
    target_id: str,
    *,
    hardware: Optional[Dict[str, Any]] = None,
    tools: Optional[List[str]] = None,
) -> str:
    return "|".join(
        [
            _aggregate_model_key(model_key_name, provider, model),
            hardware_key(hardware or {}),
            (role or "").strip() or "unknown",
            (target_id or "").strip() or "unknown",
            _tools_key(tools or []),
        ]
    )


def _relative_result_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def _numeric_stats(values: Iterable[Any]) -> Dict[str, Optional[float]]:
    nums = [_float_or_none(v) for v in values]
    nums = [v for v in nums if v is not None]
    if not nums:
        return {
            "count": 0,
            "sum": None,
            "mean": None,
            "min": None,
            "max": None,
            "median": None,
            "stdev": None,
        }
    total = round(sum(nums), 3)
    mean = round(total / len(nums), 3)
    median = round(statistics.median(nums), 3)
    stdev = round(statistics.pstdev(nums), 3) if len(nums) > 1 else 0.0
    return {
        "count": len(nums),
        "sum": total,
        "mean": mean,
        "min": round(min(nums), 3),
        "max": round(max(nums), 3),
        "median": median,
        "stdev": stdev,
    }


def _status_counts(statuses: Iterable[str]) -> Dict[str, int]:
    counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0, "other": 0}
    for raw in statuses:
        st = (raw or "other").lower()
        if st in counts:
            counts[st] += 1
        else:
            counts["other"] += 1
    return counts


def _rate(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _benchmark_attempted_observations(obs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Scoreable targets only — passes + real misses (wall-clock timeouts and
    request-budget exhaustion); provider/tool/infra aborts are excluded."""
    return [o for o in obs if is_benchmark_attempt(o)]


def _root_success_observations(obs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Observations that obtained root (primary signal for tokens-to-root metrics)."""
    attempted = _benchmark_attempted_observations(obs)
    rooted = [o for o in attempted if o.get("got_root") is True]
    if rooted:
        return rooted
    return [o for o in attempted if (o.get("status") or "").lower() == "passed"]


def _failed_observations(obs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        o
        for o in _benchmark_attempted_observations(obs)
        if o.get("got_root") is False
        or (
            o.get("got_root") is None
            and normalize_target_status(o.get("status")) == "failed"
        )
    ]


def _outcome_block(obs: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "count": len(obs),
        "elapsed_seconds": _numeric_stats(o.get("elapsed_seconds") for o in obs),
        "beroot_seconds": _numeric_stats(o.get("beroot_seconds") for o in obs),
        "ai_llm_seconds": _numeric_stats(o.get("ai_llm_seconds") for o in obs),
        "shell_seconds": _numeric_stats(o.get("shell_seconds") for o in obs),
        "other_seconds": _numeric_stats(o.get("other_seconds") for o in obs),
        "tokens_total": _numeric_stats(o.get("tokens_total") for o in obs),
        "prompt_tokens": _numeric_stats(o.get("prompt_tokens") for o in obs),
        "completion_tokens": _numeric_stats(o.get("completion_tokens") for o in obs),
        "commands_count": _numeric_stats(o.get("commands_count") for o in obs),
        "ai_requests": _numeric_stats(o.get("ai_requests") for o in obs),
    }


def _efficiency_tokens_per_second(tokens_mean: Optional[float], elapsed_mean: Optional[float]) -> Optional[float]:
    if tokens_mean is None or elapsed_mean is None or elapsed_mean <= 0:
        return None
    return round(tokens_mean / elapsed_mean, 3)


def _extract_outcome_summary(block: Dict[str, Any]) -> Dict[str, Optional[float]]:
    tokens = block.get("tokens_total") or {}
    elapsed = block.get("elapsed_seconds") or {}
    ai_requests = block.get("ai_requests") or {}
    commands = block.get("commands_count") or {}
    prompt = block.get("prompt_tokens") or {}
    completion = block.get("completion_tokens") or {}
    mean_tokens = tokens.get("mean")
    mean_elapsed = elapsed.get("mean")
    return {
        "count": block.get("count", 0),
        "mean_tokens": mean_tokens,
        "median_tokens": tokens.get("median"),
        "mean_prompt_tokens": prompt.get("mean"),
        "mean_completion_tokens": completion.get("mean"),
        "mean_elapsed_seconds": mean_elapsed,
        "median_elapsed_seconds": elapsed.get("median"),
        "mean_ai_requests": ai_requests.get("mean"),
        "mean_commands": commands.get("mean"),
        "tokens_per_second": _efficiency_tokens_per_second(mean_tokens, mean_elapsed),
    }


class _StatsAccumulator:
    """Collect target-level observations and produce aggregate metrics."""

    def __init__(self) -> None:
        self.observations: List[Dict[str, Any]] = []
        self.run_ids: set[str] = set()

    def add(
        self,
        *,
        run_id: str,
        batch_id: Optional[str],
        provider: str,
        model: str,
        model_key_name: str,
        role: str,
        target_id: str,
        status: str,
        got_root: Optional[bool],
        elapsed_seconds: Optional[float],
        timing_summary: Optional[Dict[str, Any]],
        tokens_total: Optional[int],
        prompt_tokens: Optional[int],
        completion_tokens: Optional[int],
        commands_count: Optional[int],
        ai_requests: Optional[int],
        finished_at: Optional[str],
        result_path: str,
        tools: Optional[List[str]] = None,
        hardware: Optional[Dict[str, Any]] = None,
        profile_key: str = "",
        message: str = "",
        stop_reason: str = "",
        timeline: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.run_ids.add(run_id)
        agg_key = _aggregate_model_key(model_key_name, provider, model)
        hw = hardware if isinstance(hardware, dict) else {}
        hw_key = hardware_key(hw)
        timing = timing_summary or {}
        self.observations.append(
            {
                "run_id": run_id,
                "batch_id": batch_id,
                "provider": provider,
                "model": model,
                "model_key_name": model_key_name or "",
                "model_key": agg_key,
                "model_tag": _model_key(provider, model),
                "role": role or "unknown",
                "target_id": target_id or "unknown",
                "tools": list(tools or []),
                "hardware_key": hw_key,
                "profile_key": profile_key or collaborative_profile_key(
                    model_key_name, provider, model, hw
                ),
                "scenario_key": _scenario_key(
                    model_key_name,
                    provider,
                    model,
                    role,
                    target_id,
                    hardware=hw,
                    tools=tools,
                ),
                "status": (status or "other").lower(),
                "message": message or "",
                "stop_reason": stop_reason or "",
                "timeline": list(timeline or []),
                "got_root": got_root,
                "elapsed_seconds": _float_or_none(elapsed_seconds),
                "beroot_seconds": _float_or_none(timing.get("beroot_seconds")),
                "ai_llm_seconds": _float_or_none(timing.get("ai_llm_seconds")),
                "shell_seconds": _float_or_none(timing.get("shell_seconds")),
                "other_seconds": _float_or_none(timing.get("other_seconds")),
                "tokens_total": _int_or_zero(tokens_total) if tokens_total is not None else None,
                "prompt_tokens": _int_or_zero(prompt_tokens) if prompt_tokens is not None else None,
                "completion_tokens": (
                    _int_or_zero(completion_tokens) if completion_tokens is not None else None
                ),
                "commands_count": commands_count,
                "ai_requests": ai_requests,
                "finished_at": finished_at,
                "result_path": result_path,
            }
        )

    def finalize(self) -> Dict[str, Any]:
        obs = self.observations
        statuses = [normalize_target_status(o.get("status")) for o in obs]
        counts = _status_counts(statuses)
        total = len(obs)
        attempted_obs = _benchmark_attempted_observations(obs)
        attempted = len(attempted_obs)
        # Root rate uses scoreable attempts only (pass + timeout), not provider aborts.
        got_root_true = sum(1 for o in attempted_obs if o.get("got_root") is True)
        got_root_known = sum(1 for o in attempted_obs if o.get("got_root") is not None)
        root_obs = _root_success_observations(obs)
        failed_obs = _failed_observations(obs)
        got_root_block = _outcome_block(root_obs)
        failed_block = _outcome_block(failed_obs)
        got_root_summary = _extract_outcome_summary(got_root_block)

        return {
            "observations": total,
            "attempted": attempted,
            "runs": len(self.run_ids),
            "passed": counts["passed"],
            "failed": counts["failed"],
            "error": counts["error"],
            "skipped": counts["skipped"],
            "other": counts["other"],
            "pass_rate": _rate(counts["passed"], attempted),
            "got_root_count": got_root_true,
            "got_root_known": got_root_known,
            "got_root_rate": _rate(got_root_true, got_root_known),
            "elapsed_seconds": _numeric_stats(o.get("elapsed_seconds") for o in attempted_obs),
            "beroot_seconds": _numeric_stats(o.get("beroot_seconds") for o in attempted_obs),
            "ai_llm_seconds": _numeric_stats(o.get("ai_llm_seconds") for o in attempted_obs),
            "shell_seconds": _numeric_stats(o.get("shell_seconds") for o in attempted_obs),
            "other_seconds": _numeric_stats(o.get("other_seconds") for o in attempted_obs),
            "tokens_total": _numeric_stats(o.get("tokens_total") for o in attempted_obs),
            "prompt_tokens": _numeric_stats(o.get("prompt_tokens") for o in attempted_obs),
            "completion_tokens": _numeric_stats(o.get("completion_tokens") for o in attempted_obs),
            "commands_count": _numeric_stats(o.get("commands_count") for o in attempted_obs),
            "ai_requests": _numeric_stats(o.get("ai_requests") for o in attempted_obs),
            "got_root": got_root_block,
            "failed_outcomes": failed_block,
            "mean_tokens_to_root": got_root_summary.get("mean_tokens"),
            "median_tokens_to_root": got_root_summary.get("median_tokens"),
            "mean_prompt_tokens_to_root": got_root_summary.get("mean_prompt_tokens"),
            "mean_completion_tokens_to_root": got_root_summary.get("mean_completion_tokens"),
            "mean_elapsed_to_root": got_root_summary.get("mean_elapsed_seconds"),
            "median_elapsed_to_root": got_root_summary.get("median_elapsed_seconds"),
            "mean_ai_requests_to_root": got_root_summary.get("mean_ai_requests"),
            "mean_commands_to_root": got_root_summary.get("mean_commands"),
            "tokens_per_second_to_root": got_root_summary.get("tokens_per_second"),
        }


def discover_result_documents(
    results_dir: Optional[Path] = None,
) -> List[Tuple[Path, Dict[str, Any]]]:
    """Find every result.json under the results tree."""
    root = results_dir or BENCHMARK_RESULTS_DIR
    if not root.is_dir():
        return []

    found: List[Tuple[Path, Dict[str, Any]]] = []
    for path in sorted(root.rglob("result.json")):
        if not path.is_file():
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _log_warning(f"skipping unreadable result {path}: {exc}")
            continue
        if not isinstance(doc, dict):
            continue
        found.append((path, doc))
    return found


def _dedupe_runs(docs: List[Tuple[Path, Dict[str, Any]]]) -> List[Tuple[Path, Dict[str, Any]]]:
    """Keep the newest finished_at per run id (handles re-runs / duplicate imports)."""
    best: Dict[str, Tuple[Path, Dict[str, Any], Optional[datetime]]] = {}
    for path, doc in docs:
        run_id = str(doc.get("id") or path.parent.name)
        finished = _parse_ts(doc.get("finished_at")) or _parse_ts(doc.get("started_at"))
        prev = best.get(run_id)
        if prev is None or (finished and (prev[2] is None or finished >= prev[2])):
            best[run_id] = (path, doc, finished)
    return [(path, doc) for path, doc, _ in best.values()]


def _extract_observations(
    path: Path,
    doc: Dict[str, Any],
    accumulator: _StatsAccumulator,
    *,
    by_model: Dict[str, _StatsAccumulator],
    by_profile: Dict[str, _StatsAccumulator],
    by_role: Dict[str, _StatsAccumulator],
    by_target: Dict[str, _StatsAccumulator],
    by_scenario: Dict[str, _StatsAccumulator],
) -> None:
    run_id = str(doc.get("id") or path.parent.name)
    batch_id = doc.get("batch_id")
    provider = str(doc.get("provider") or "")
    model = str(doc.get("model") or "")
    model_key_name = str(doc.get("model_key_name") or "")
    role = str(doc.get("role_objective") or "")
    hardware = normalize_stored_hardware(
        provider,
        doc.get("hardware") if isinstance(doc.get("hardware"), dict) else {},
    )
    run_tools = _tools_from_doc(doc)
    finished_at = doc.get("finished_at")
    result_path = _relative_result_path(path)
    profile_key = collaborative_profile_key(model_key_name, provider, model, hardware)

    for target in doc.get("targets") or []:
        if not isinstance(target, dict):
            continue
        t_provider = str(target.get("provider") or provider)
        t_model = str(target.get("model") or model)
        t_model_key_name = str(target.get("model_key_name") or model_key_name)
        t_role = str(target.get("role_objective") or role)
        target_id = str(target.get("target_id") or "unknown")
        stop_reason = str(target.get("stop_reason") or "").strip()
        if not stop_reason:
            for entry in target.get("timeline") or []:
                if isinstance(entry, dict) and entry.get("stop_reason"):
                    stop_reason = str(entry.get("stop_reason") or "").strip()
                    if stop_reason:
                        break
        kwargs = dict(
            run_id=run_id,
            batch_id=batch_id,
            provider=t_provider,
            model=t_model,
            model_key_name=t_model_key_name,
            role=t_role,
            target_id=target_id,
            status=str(target.get("status") or "other"),
            got_root=target.get("got_root"),
            elapsed_seconds=target.get("elapsed_seconds"),
            timing_summary=target.get("timing_summary") or {},
            tokens_total=target.get("tokens_total"),
            prompt_tokens=target.get("prompt_tokens"),
            completion_tokens=target.get("completion_tokens"),
            commands_count=target.get("commands_count"),
            ai_requests=target.get("ai_requests"),
            finished_at=finished_at,
            result_path=result_path,
            tools=run_tools,
            hardware=hardware,
            profile_key=profile_key,
            message=str(target.get("message") or ""),
            stop_reason=stop_reason,
            timeline=list(target.get("timeline") or []),
        )
        accumulator.add(**kwargs)
        by_model.setdefault(
            _aggregate_model_key(t_model_key_name, t_provider, t_model),
            _StatsAccumulator(),
        ).add(**kwargs)
        by_profile.setdefault(profile_key, _StatsAccumulator()).add(**kwargs)
        by_role.setdefault(t_role or "unknown", _StatsAccumulator()).add(**kwargs)
        by_target.setdefault(target_id, _StatsAccumulator()).add(**kwargs)
        by_scenario.setdefault(
            _scenario_key(
                t_model_key_name,
                t_provider,
                t_model,
                t_role,
                target_id,
                hardware=hardware,
                tools=run_tools,
            ),
            _StatsAccumulator(),
        ).add(**kwargs)


def _positive_or_none(value: Any) -> Optional[float]:
    """Return float when value is a usable positive metric; else None."""
    try:
        if value is None:
            return None
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num <= 0:
        return None
    return num


def _stats_ranking_fields(stats: Dict[str, Any]) -> Dict[str, Any]:
    mean_prompt = (stats.get("prompt_tokens") or {}).get("mean")
    mean_prompt_to_root = stats.get("mean_prompt_tokens_to_root")
    mean_tokens_to_root = stats.get("mean_tokens_to_root")
    return {
        "observations": stats.get("observations", 0),
        "attempted": stats.get("attempted", 0),
        "runs": stats.get("runs", 0),
        "pass_rate": stats.get("pass_rate"),
        "got_root_rate": stats.get("got_root_rate"),
        "got_root_count": stats.get("got_root_count", 0),
        "got_root_known": stats.get("got_root_known", 0),
        "median_elapsed_seconds": (stats.get("elapsed_seconds") or {}).get("median"),
        "mean_elapsed_seconds": (stats.get("elapsed_seconds") or {}).get("mean"),
        "mean_tokens_total": (stats.get("tokens_total") or {}).get("mean"),
        "mean_prompt_tokens": mean_prompt,
        "mean_prompt_tokens_to_root": mean_prompt_to_root,
        # Zero token telemetry is treated as missing for efficiency rankings.
        "usable_mean_prompt_tokens": _positive_or_none(mean_prompt),
        "usable_mean_prompt_tokens_to_root": _positive_or_none(mean_prompt_to_root),
        "usable_mean_tokens_to_root": _positive_or_none(mean_tokens_to_root),
        "mean_tokens_to_root": mean_tokens_to_root,
        "median_tokens_to_root": stats.get("median_tokens_to_root"),
        "mean_elapsed_to_root": stats.get("mean_elapsed_to_root"),
        "median_elapsed_to_root": stats.get("median_elapsed_to_root"),
        "mean_ai_requests_to_root": stats.get("mean_ai_requests_to_root"),
        "mean_commands_to_root": stats.get("mean_commands_to_root"),
        "tokens_per_second_to_root": stats.get("tokens_per_second_to_root"),
        "usable_tokens_per_second_to_root": _positive_or_none(
            stats.get("tokens_per_second_to_root")
        ),
    }


def _ranking_row_from_stats(
    profile_key: str,
    stats: Dict[str, Any],
    *,
    hardware_labels: Optional[Dict[str, str]] = None,
    hardware_by_key: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    parsed = parse_profile_key(profile_key)
    hw_key = parsed["hardware_key"]
    labels = hardware_labels or {}
    hw_by_key = hardware_by_key or {}
    model_key = parsed["model_key_name"]
    return {
        "profile_key": profile_key,
        "profile_label": profile_display_label(model_key, hw_by_key.get(hw_key, {})),
        "model_key_name": model_key,
        "hardware_key": hw_key,
        "hardware_label": labels.get(hw_key, hw_key),
        "model": model_key,
        **_stats_ranking_fields(stats),
    }


def _model_ranking_row(model_key: str, stats: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "model_key_name": model_key,
        "profile_label": model_key,
        "model": model_key,
        **_stats_ranking_fields(stats),
    }


def _rank_profiles(
    by_profile: Dict[str, Dict[str, Any]],
    *,
    hardware_labels: Optional[Dict[str, str]] = None,
    hardware_by_key: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    rows: List[Dict[str, Any]] = [
        _ranking_row_from_stats(
            profile_key,
            stats,
            hardware_labels=hardware_labels,
            hardware_by_key=hardware_by_key,
        )
        for profile_key, stats in by_profile.items()
    ]
    return _sorted_ranking_views(rows)


def _rank_models(by_model: Dict[str, Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Legacy model-only rankings (cross-hardware rollup)."""
    rows: List[Dict[str, Any]] = [
        _model_ranking_row(model_key, stats) for model_key, stats in by_model.items()
    ]
    return _sorted_ranking_views(rows)


def _sorted_ranking_views(rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    return {
        "by_got_root_count": sorted(
            rows,
            key=lambda r: (
                -(r.get("got_root_count") or 0),
                r.get("got_root_rate") is None,
                -(r.get("got_root_rate") or 0),
                -(r.get("attempted") or 0),
                str(r.get("profile_label") or r.get("model_key_name") or ""),
            ),
        ),
        "by_pass_rate": sorted(
            rows,
            key=lambda r: (r.get("pass_rate") is None, -(r.get("pass_rate") or 0)),
        ),
        "by_got_root_rate": sorted(
            rows,
            key=lambda r: (r.get("got_root_rate") is None, -(r.get("got_root_rate") or 0)),
        ),
        "by_median_elapsed": sorted(
            rows,
            key=lambda r: (
                r.get("median_elapsed_seconds") is None,
                r.get("median_elapsed_seconds") if r.get("median_elapsed_seconds") is not None else 0,
            ),
        ),
        "by_tokens_to_root": sorted(
            rows,
            key=lambda r: (
                r.get("usable_mean_tokens_to_root") is None,
                r.get("usable_mean_tokens_to_root")
                if r.get("usable_mean_tokens_to_root") is not None
                else 0,
            ),
        ),
    }


def _rank_scenarios(
    by_scenario: Dict[str, Dict[str, Any]],
    *,
    hardware_labels: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    labels = hardware_labels or {}
    for scenario_key, stats in by_scenario.items():
        parsed = _parse_scenario_key(scenario_key)
        hw_key = parsed["hardware_key"]
        rows.append(
            {
                "scenario": scenario_key,
                "model": parsed["model"],
                "hardware_key": hw_key,
                "hardware_label": labels.get(hw_key, hw_key),
                "role": parsed["role"],
                "target_id": parsed["target_id"],
                "tools": parsed["tools"],
                "observations": stats.get("observations", 0),
                "attempted": stats.get("attempted", 0),
                "runs": stats.get("runs", 0),
                "pass_rate": stats.get("pass_rate"),
                "got_root_rate": stats.get("got_root_rate"),
                "got_root_count": stats.get("got_root_count", 0),
                "median_elapsed_seconds": (stats.get("elapsed_seconds") or {}).get("median"),
                "mean_elapsed_seconds": (stats.get("elapsed_seconds") or {}).get("mean"),
                "mean_ai_llm_seconds": (stats.get("ai_llm_seconds") or {}).get("mean"),
                "mean_shell_seconds": (stats.get("shell_seconds") or {}).get("mean"),
                "mean_tokens_total": (stats.get("tokens_total") or {}).get("mean"),
                "mean_tokens_to_root": stats.get("mean_tokens_to_root"),
                "median_tokens_to_root": stats.get("median_tokens_to_root"),
                "mean_elapsed_to_root": stats.get("mean_elapsed_to_root"),
                "mean_ai_requests_to_root": stats.get("mean_ai_requests_to_root"),
                "mean_commands_to_root": stats.get("mean_commands_to_root"),
                "tokens_per_second_to_root": stats.get("tokens_per_second_to_root"),
            }
        )
    rows.sort(
        key=lambda r: (r.get("pass_rate") is None, -(r.get("pass_rate") or 0), r.get("scenario") or ""),
    )
    return rows


def build_master_document(
    results_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Scan all result.json files and build the collaborative master aggregate."""
    root = results_dir or BENCHMARK_RESULTS_DIR
    raw_docs = discover_result_documents(root)
    docs = _dedupe_runs(raw_docs)

    overall = _StatsAccumulator()
    by_model: Dict[str, _StatsAccumulator] = {}
    by_profile: Dict[str, _StatsAccumulator] = {}
    by_role: Dict[str, _StatsAccumulator] = {}
    by_target: Dict[str, _StatsAccumulator] = {}
    by_scenario: Dict[str, _StatsAccumulator] = {}

    runs_index: List[Dict[str, Any]] = []
    model_key_names: set[str] = set()
    model_tags: set[str] = set()
    roles: set[str] = set()
    targets: set[str] = set()
    providers: set[str] = set()
    hosts: set[str] = set()
    hardware_profiles: List[Dict[str, Any]] = []
    hardware_seen: set[str] = set()
    hardware_by_key: Dict[str, Dict[str, Any]] = {}
    hardware_labels: Dict[str, str] = {}
    tool_ids: set[str] = set()
    tool_profiles: set[str] = set()

    for path, doc in docs:
        provider = str(doc.get("provider") or "")
        model = str(doc.get("model") or "")
        model_key_name = str(doc.get("model_key_name") or "")
        role = str(doc.get("role_objective") or "unknown")
        if provider:
            providers.add(provider)
        if model:
            model_tags.add(_model_key(provider, model))
        agg_key = _aggregate_model_key(model_key_name, provider, model)
        if agg_key:
            model_key_names.add(agg_key)
        if role:
            roles.add(role)
        if doc.get("host"):
            hosts.add(str(doc.get("host")))
        for target in doc.get("targets") or []:
            if isinstance(target, dict) and target.get("target_id"):
                targets.add(str(target["target_id"]))
        hardware = normalize_stored_hardware(
            provider,
            doc.get("hardware") if isinstance(doc.get("hardware"), dict) else {},
        )
        if hardware:
            hw_key = hardware_key(hardware)
            hw_identity = hardware_identity(hardware)
            hw_json = json.dumps(hw_identity, sort_keys=True, default=str)
            if hw_json not in hardware_seen:
                hardware_seen.add(hw_json)
                hardware_profiles.append(hardware)
            if hw_key not in hardware_by_key and hw_identity:
                hardware_by_key[hw_key] = hw_identity
                hardware_labels[hw_key] = hardware_label(hardware)

        run_tools = _tools_from_doc(doc)
        tool_ids.update(run_tools)
        tool_profiles.add(_tools_key(run_tools))
        profile_key = collaborative_profile_key(model_key_name, provider, model, hardware)

        _extract_observations(
            path,
            doc,
            overall,
            by_model=by_model,
            by_profile=by_profile,
            by_role=by_role,
            by_target=by_target,
            by_scenario=by_scenario,
        )

        runs_index.append(
            {
                "id": doc.get("id"),
                "batch_id": doc.get("batch_id"),
                "repetition": doc.get("repetition"),
                "repetitions": doc.get("repetitions"),
                "phase": doc.get("phase"),
                "mode": doc.get("mode"),
                "host": doc.get("host"),
                "provider": provider,
                "model": model,
                "model_key_name": agg_key,
                "model_key": _model_key(provider, model),
                "profile_key": profile_key,
                "profile_label": profile_display_label(agg_key, hardware),
                "hardware_key": hardware_key(hardware),
                "model_registry_path": (doc.get("model_registry") or {}).get("registry_path"),
                "hardware": hardware,
                "role_objective": doc.get("role_objective") or role,
                "tools": run_tools,
                "started_at": doc.get("started_at"),
                "finished_at": doc.get("finished_at"),
                "result_path": _relative_result_path(path),
                "summary": doc.get("summary") or {},
            }
        )

    runs_index.sort(
        key=lambda r: _parse_ts(r.get("finished_at"))
        or _parse_ts(r.get("started_at"))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    by_model_out = {k: v.finalize() for k, v in sorted(by_model.items())}
    by_profile_out = {k: v.finalize() for k, v in sorted(by_profile.items())}
    by_role_out = {k: v.finalize() for k, v in sorted(by_role.items())}
    by_target_out = {k: v.finalize() for k, v in sorted(by_target.items())}
    by_scenario_out = {k: v.finalize() for k, v in sorted(by_scenario.items())}

    return {
        "schema_version": MASTER_RESULT_SCHEMA_VERSION,
        "updated_at": _utcnow_iso(),
        "results_root": _relative_result_path(root),
        "source_files_scanned": len(raw_docs),
        "source_runs_deduped": len(docs),
        "catalog": {
            "providers": sorted(providers),
            "model_key_names": sorted(model_key_names),
            "model_tags": sorted(model_tags),
            "roles": sorted(roles),
            "targets": sorted(targets),
            "hosts": sorted(hosts),
            "hardware_profiles": hardware_profiles,
            "hardware_by_key": hardware_by_key,
            "tools": sorted(tool_ids),
            "tool_profiles": sorted(tool_profiles),
        },
        "runs_index": runs_index,
        "aggregate": {
            "overall": overall.finalize(),
            "by_model": by_model_out,
            "by_profile": by_profile_out,
            "by_role": by_role_out,
            "by_target": by_target_out,
            "by_scenario": by_scenario_out,
        },
        "rankings": {
            "profiles": _rank_profiles(
                by_profile_out,
                hardware_labels=hardware_labels,
                hardware_by_key=hardware_by_key,
            ),
            "models": _rank_models(by_model_out),
            "scenarios": _rank_scenarios(by_scenario_out, hardware_labels=hardware_labels),
        },
    }


def _format_rate(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


def _format_num(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:.3f}"


def _format_int(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{int(round(value)):,}"


def _format_tools(tools: Optional[List[str]]) -> str:
    if not tools:
        return "—"
    return ", ".join(f"`{tool}`" for tool in tools)


def _format_overall_metrics_table(stats: Dict[str, Any]) -> List[str]:
    """Markdown metric table rows for one aggregate stats block (e.g. per model key)."""
    elapsed = stats.get("elapsed_seconds") or {}
    return [
        "| Metric | Value |",
        "|--------|------:|",
        f"| Attempted (n) | {stats.get('attempted', 0)} |",
        f"| Runs | {stats.get('runs', 0)} |",
        f"| Pass rate (attempted) | {_format_rate(stats.get('pass_rate'))} |",
        f"| Got root rate | {_format_rate(stats.get('got_root_rate'))} |",
        f"| Got root count | {stats.get('got_root_count', 0)} |",
        f"| Median elapsed (s) | {_format_num(elapsed.get('median'))} |",
        f"| Mean elapsed (s) | {_format_num(elapsed.get('mean'))} |",
        f"| Mean tokens to root | {_format_int(stats.get('mean_tokens_to_root'))} |",
        f"| Median tokens to root | {_format_int(stats.get('median_tokens_to_root'))} |",
        f"| Mean elapsed to root (s) | {_format_num(stats.get('mean_elapsed_to_root'))} |",
        f"| Mean AI requests to root | {_format_num(stats.get('mean_ai_requests_to_root'))} |",
        f"| Mean commands to root | {_format_num(stats.get('mean_commands_to_root'))} |",
        f"| Tokens/sec to root | {_format_num(stats.get('tokens_per_second_to_root'))} |",
    ]


def _hardware_labels_from_catalog(catalog: Dict[str, Any]) -> Dict[str, str]:
    labels: Dict[str, str] = {}
    for profile in catalog.get("hardware_profiles") or []:
        if isinstance(profile, dict):
            key = hardware_key(profile)
            labels[key] = hardware_label(profile)
    for key, profile in (catalog.get("hardware_by_key") or {}).items():
        if key not in labels and isinstance(profile, dict):
            labels[str(key)] = hardware_label(profile)
    return labels


def _hardware_by_key_from_catalog(catalog: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for key, profile in (catalog.get("hardware_by_key") or {}).items():
        if isinstance(profile, dict):
            out[str(key)] = profile
    for profile in catalog.get("hardware_profiles") or []:
        if isinstance(profile, dict):
            out.setdefault(hardware_key(profile), hardware_identity(profile) or profile)
    return out


def _profile_overall_heading(
    profile_key: str,
    hardware_by_key: Dict[str, Dict[str, Any]],
) -> str:
    parsed = parse_profile_key(profile_key)
    label = profile_display_label(
        parsed["model_key_name"],
        hardware_by_key.get(parsed["hardware_key"], {}),
    )
    return f"#### Overall — {label}"


def format_master_summary(master: Dict[str, Any]) -> str:
    """Human-readable rankings and stats for the master document."""
    lines: List[str] = [
        "Benchmark master results (collaborative aggregate)",
        f"updated_at={master.get('updated_at')}",
        f"runs={master.get('source_runs_deduped')} "
        f"(from {master.get('source_files_scanned')} result file(s))",
        "",
    ]

    catalog = master.get("catalog") or {}
    lines.extend(
        [
            "Catalog:",
            f"  model_key_names ({len(catalog.get('model_key_names') or [])}): "
            f"{', '.join(catalog.get('model_key_names') or [])}",
            f"  model_tags ({len(catalog.get('model_tags') or [])}): "
            f"{', '.join(catalog.get('model_tags') or [])}",
            f"  roles ({len(catalog.get('roles') or [])}): {', '.join(catalog.get('roles') or [])}",
            f"  targets ({len(catalog.get('targets') or [])}): {', '.join(catalog.get('targets') or [])}",
            "",
        ]
    )

    overall = (master.get("aggregate") or {}).get("overall") or {}
    by_profile = (master.get("aggregate") or {}).get("by_profile") or {}
    hardware_by_key = _hardware_by_key_from_catalog(catalog)
    if by_profile:
        for profile_key in sorted(by_profile.keys()):
            stats = by_profile[profile_key]
            label = profile_display_label(
                parse_profile_key(profile_key)["model_key_name"],
                hardware_by_key.get(parse_profile_key(profile_key)["hardware_key"], {}),
            )
            lines.extend(
                [
                    f"Overall ({label}):",
                    f"  profile_key={profile_key}",
                    f"  attempted={stats.get('attempted')} runs={stats.get('runs')}",
                    f"  pass_rate={_format_rate(stats.get('pass_rate'))} "
                    f"got_root_rate={_format_rate(stats.get('got_root_rate'))}",
                    f"  elapsed median={_format_num((stats.get('elapsed_seconds') or {}).get('median'))}s "
                    f"mean={_format_num((stats.get('elapsed_seconds') or {}).get('mean'))}s",
                    f"  tokens_to_root mean={_format_int(stats.get('mean_tokens_to_root'))} "
                    f"median={_format_int(stats.get('median_tokens_to_root'))} "
                    f"(n={((stats.get('got_root') or {}).get('count')) or 0})",
                    f"  elapsed_to_root mean={_format_num(stats.get('mean_elapsed_to_root'))}s "
                    f"ai_requests={_format_num(stats.get('mean_ai_requests_to_root'))} "
                    f"commands={_format_num(stats.get('mean_commands_to_root'))}",
                    "",
                ]
            )
    else:
        lines.extend(
            [
                "Overall:",
                f"  attempted={overall.get('attempted')} runs={overall.get('runs')}",
                f"  pass_rate={_format_rate(overall.get('pass_rate'))} "
                f"got_root_rate={_format_rate(overall.get('got_root_rate'))}",
                f"  elapsed median={_format_num((overall.get('elapsed_seconds') or {}).get('median'))}s "
                f"mean={_format_num((overall.get('elapsed_seconds') or {}).get('mean'))}s",
                f"  tokens_to_root mean={_format_int(overall.get('mean_tokens_to_root'))} "
                f"median={_format_int(overall.get('median_tokens_to_root'))} "
                f"(n={((overall.get('got_root') or {}).get('count')) or 0})",
                f"  elapsed_to_root mean={_format_num(overall.get('mean_elapsed_to_root'))}s "
                f"ai_requests={_format_num(overall.get('mean_ai_requests_to_root'))} "
                f"commands={_format_num(overall.get('mean_commands_to_root'))}",
                "",
            ]
        )

    lines.append("Profiles (model · hardware) by pass rate:")
    for row in (master.get("rankings") or {}).get("profiles", {}).get("by_pass_rate") or []:
        lines.append(
            f"  {row.get('profile_label') or row.get('model_key_name')}: "
            f"pass={_format_rate(row.get('pass_rate'))} "
            f"got_root={_format_rate(row.get('got_root_rate'))} "
            f"n={row.get('attempted')} "
            f"median_elapsed={_format_num(row.get('median_elapsed_seconds'))}s "
            f"tokens_to_root={_format_int(row.get('mean_tokens_to_root'))}"
        )
    lines.append("")

    lines.append("Scenarios (model · hardware · role · target · tools) by pass rate:")
    for row in (master.get("rankings") or {}).get("scenarios") or []:
        lines.append(
            f"  {row.get('scenario')}: pass={_format_rate(row.get('pass_rate'))} "
            f"got_root={_format_rate(row.get('got_root_rate'))} "
            f"hw={row.get('hardware_label')} "
            f"tools={','.join(row.get('tools') or []) or 'none'} "
            f"n={row.get('attempted')} "
            f"tokens_to_root={_format_int(row.get('mean_tokens_to_root'))} "
            f"elapsed_to_root={_format_num(row.get('mean_elapsed_to_root'))}s "
            f"ai_req={_format_num(row.get('mean_ai_requests_to_root'))}"
        )
    lines.append("")

    return "\n".join(lines) + "\n"


def _format_scenarios_markdown_table(
    master: Dict[str, Any],
    *,
    hardware_by_key: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Markdown lines for the scenarios ranking table (may be empty)."""
    scenario_rows = (master.get("rankings") or {}).get("scenarios") or []
    if not scenario_rows:
        return []

    if hardware_by_key is None:
        hardware_by_key = _hardware_by_key_from_catalog(master.get("catalog") or {})

    lines = [
        "#### Scenarios (profile · role · target · tools)",
        "",
        "| Profile | Role | Target | Tools | n | Pass | Got root | Tokens→root | Elapsed→root (s) | AI req | Commands |",
        "|---------|------|--------|-------|--:|-----:|---------:|------------:|-----------------:|-------:|---------:|",
    ]
    for row in scenario_rows:
        scenario_profile = profile_display_label(
            row.get("model") or "",
            hardware_by_key.get(row.get("hardware_key") or "", {}),
        )
        lines.append(
            f"| {scenario_profile} "
            f"| {row.get('role')} "
            f"| `{row.get('target_id')}` "
            f"| {_format_tools(row.get('tools'))} "
            f"| {row.get('attempted', 0)} "
            f"| {_format_rate(row.get('pass_rate'))} "
            f"| {_format_rate(row.get('got_root_rate'))} "
            f"| {_format_int(row.get('mean_tokens_to_root'))} "
            f"| {_format_num(row.get('mean_elapsed_to_root'))} "
            f"| {_format_num(row.get('mean_ai_requests_to_root'))} "
            f"| {_format_num(row.get('mean_commands_to_root'))} |"
        )
    lines.append("")
    return lines


def format_master_markdown(
    master: Dict[str, Any],
    *,
    include_scenarios: bool = False,
    include_overall: bool = True,
) -> str:
    """GitHub-friendly markdown tables (scenarios optional; off for README).

    When ``include_overall`` is False (README), skip catalog/identity/Overall
    metric blocks and start at the Profiles ranking tables.
    """
    runs = int(master.get("source_runs_deduped") or 0)
    lines: List[str] = [
        f"_Last updated: {master.get('updated_at') or '—'} · "
        f"{runs} run(s) · "
        f"[full JSON](data/benchmark/results/master.json)_",
        "",
        "**Pass** is the percentage of scoreable attempts in which the model "
        "successfully escalated privileges to root.",
        "",
    ]

    if runs <= 0:
        lines.extend(
            [
                "_No benchmark runs yet._",
                "",
                "Run the suite from the **Benchmark** UI to create per-run sheets under "
                "`data/benchmark/results/` and populate this section. "
                "See [`data/benchmark/examples/`](data/benchmark/examples/) for sample file formats only.",
                "",
            ]
        )
        return "\n".join(lines)

    catalog = master.get("catalog") or {}
    by_profile = (master.get("aggregate") or {}).get("by_profile") or {}
    hardware_by_key = _hardware_by_key_from_catalog(catalog)

    if include_overall:
        lines.extend(
            [
                "**Catalog:** "
                f"{len(catalog.get('model_key_names') or [])} model key(s), "
                f"{len(by_profile)} profile(s) (model + hardware), "
                f"{len(catalog.get('roles') or [])} role(s), "
                f"{len(catalog.get('targets') or [])} target(s), "
                f"{len(catalog.get('tools') or [])} tool(s), "
                f"{len(catalog.get('hardware_profiles') or [])} hardware profile(s)",
                "",
                "_Identity: **model `key_name`** = weights + modelfile params (registry). "
                "**Profile** = model `key_name` · GPU lab (`BENCHMARK_GPU_*`). "
                "Runs merge when profile + role + target + tools all match._",
                "",
            ]
        )

        for profile_key in sorted(by_profile.keys()):
            stats = by_profile[profile_key]
            lines.extend(
                [
                    _profile_overall_heading(profile_key, hardware_by_key),
                    "",
                    *_format_overall_metrics_table(stats),
                    "",
                ]
            )

    profile_rows = (master.get("rankings") or {}).get("profiles", {}).get("by_pass_rate") or []
    if profile_rows:
        lines.extend(
            [
                "#### Profiles",
                "",
                "| Profile | n | Pass | Median (s) | Tokens→root | Elapsed→root (s) | AI req→root |",
                "|---------|--:|-----:|-----------:|------------:|-----------------:|------------:|",
            ]
        )
        for row in profile_rows:
            lines.append(
                f"| {row.get('profile_label') or row.get('model_key_name')} "
                f"| {row.get('attempted', 0)} "
                f"| {_format_rate(row.get('pass_rate'))} "
                f"| {_format_num(row.get('median_elapsed_seconds'))} "
                f"| {_format_int(row.get('mean_tokens_to_root'))} "
                f"| {_format_num(row.get('mean_elapsed_to_root'))} "
                f"| {_format_num(row.get('mean_ai_requests_to_root'))} |"
            )
        lines.append("")

    token_eff_rows = (master.get("rankings") or {}).get("profiles", {}).get("by_tokens_to_root") or []
    if token_eff_rows:
        lines.extend(
            [
                "#### Most token-efficient profiles (lowest mean tokens to root)",
                "",
                "| Profile | Tokens→root | Pass | n |",
                "|---------|------------:|-----:|--:|",
            ]
        )
        for row in token_eff_rows[:10]:
            if row.get("mean_tokens_to_root") is None:
                continue
            lines.append(
                f"| {row.get('profile_label') or row.get('model_key_name')} "
                f"| {_format_int(row.get('mean_tokens_to_root'))} "
                f"| {_format_rate(row.get('pass_rate'))} "
                f"| {row.get('attempted', 0)} |"
            )
        lines.append("")

    if include_scenarios:
        lines.extend(
            _format_scenarios_markdown_table(master, hardware_by_key=hardware_by_key)
        )

    return "\n".join(lines)


def _readme_has_benchmark_markers(readme: str) -> bool:
    return README_BENCHMARK_START in readme and README_BENCHMARK_END in readme


def _insert_after_first_intro_rule(readme: str, block: str) -> Optional[str]:
    """Insert ``block`` after the first top-level ``---`` following the title."""
    match = re.search(r"(?m)^---\s*$", readme)
    if not match:
        return None
    insert_at = match.end()
    prefix = readme[:insert_at].rstrip("\n")
    suffix = readme[insert_at:].lstrip("\n")
    return f"{prefix}\n\n{block.rstrip()}\n\n{suffix}"


def _append_markers_under_heading(readme: str) -> Optional[str]:
    """Place empty markers at the end of the collaborative results section."""
    heading_match = re.search(
        rf"(?m)^{re.escape(README_BENCHMARK_HEADING)}\s*$",
        readme,
    )
    if not heading_match:
        return None

    after_heading = readme[heading_match.end() :]
    # End of this section: next top-level heading or horizontal rule.
    end_match = re.search(r"(?m)^(?:##\s|---\s*$)", after_heading)
    if end_match:
        insert_at = heading_match.end() + end_match.start()
        prefix = readme[:insert_at].rstrip("\n")
        suffix = readme[insert_at:].lstrip("\n")
        markers = f"{README_BENCHMARK_START}\n{README_BENCHMARK_END}"
        return f"{prefix}\n\n{markers}\n\n{suffix}"

    prefix = readme.rstrip("\n")
    markers = f"{README_BENCHMARK_START}\n{README_BENCHMARK_END}"
    return f"{prefix}\n\n{markers}\n"


def ensure_readme_benchmark_markers(readme: str) -> Tuple[str, bool]:
    """
    Ensure README contains the collaborative stats heading + splice markers.

    Expected layout (project README): intro → ``---`` →
    ``## Collaborative benchmark results`` → markers → outro prose → rest of docs.

    Returns ``(readme, changed)``.
    """
    if _readme_has_benchmark_markers(readme):
        return readme, False

    under_heading = _append_markers_under_heading(readme)
    if under_heading is not None:
        _log_info(
            f"inserted {README_BENCHMARK_START}/{README_BENCHMARK_END} "
            f"under {README_BENCHMARK_HEADING!r}"
        )
        return under_heading, True

    section = (
        f"{README_BENCHMARK_HEADING}\n\n"
        f"{README_BENCHMARK_START}\n"
        f"{README_BENCHMARK_END}\n\n"
        f"{README_BENCHMARK_SECTION_OUTRO}"
    )
    inserted = _insert_after_first_intro_rule(readme, section)
    if inserted is not None:
        _log_info(
            f"created {README_BENCHMARK_HEADING!r} after intro rule "
            f"with {README_BENCHMARK_START}/{README_BENCHMARK_END}"
        )
        return inserted, True

    # Last resort: append at end of file.
    _log_warning(
        "could not find intro --- or collaborative heading; "
        "appending benchmark markers at end of README"
    )
    suffix = (
        f"\n\n{README_BENCHMARK_HEADING}\n\n"
        f"{README_BENCHMARK_START}\n"
        f"{README_BENCHMARK_END}\n\n"
        f"{README_BENCHMARK_SECTION_OUTRO}"
    )
    return readme.rstrip("\n") + suffix, True


def ensure_readme_benchmark_outro(readme: str) -> Tuple[str, bool]:
    """Place collaborative outro prose after the master end marker (not before it)."""
    if README_BENCHMARK_END not in readme:
        return readme, False

    # Drop leftover prose between the heading and the start marker.
    heading_pat = re.compile(
        rf"(?ms)^({re.escape(README_BENCHMARK_HEADING)}\s*\n)"
        rf"(.*?)"
        rf"({re.escape(README_BENCHMARK_START)})"
    )

    def _trim_between(match: re.Match[str]) -> str:
        between = match.group(2)
        # Keep only blank lines; drop explanatory prose that used to live here.
        if between.strip():
            return f"{match.group(1)}\n{match.group(3)}"
        return match.group(0)

    trimmed = heading_pat.sub(_trim_between, readme, count=1)

    end_idx = trimmed.find(README_BENCHMARK_END)
    if end_idx < 0:
        return trimmed, trimmed != readme
    after_end = end_idx + len(README_BENCHMARK_END)
    prefix = trimmed[:after_end]
    suffix = trimmed[after_end:]

    # Remove an existing copy of the outro if present immediately after the marker.
    # Match until the next top-level heading or horizontal rule.
    suffix_lstrip = suffix.lstrip("\n")
    next_break = re.search(r"(?m)^(?:##\s|---\s*$)", suffix_lstrip)
    head = suffix_lstrip[: next_break.start()] if next_break else suffix_lstrip
    rest = suffix_lstrip[next_break.start() :] if next_break else ""

    # If head already looks like our outro (starts with Live stats), replace it.
    # Otherwise, if head is empty/whitespace-only, just insert. If head has other
    # content that isn't the outro, insert outro before that content only when
    # head is blank — keep unknown content.
    outro = README_BENCHMARK_SECTION_OUTRO.rstrip() + "\n"
    if head.strip().startswith("**Live stats only**"):
        new_suffix = f"\n\n{outro}\n{rest.lstrip()}" if rest else f"\n\n{outro}"
    elif not head.strip():
        new_suffix = f"\n\n{outro}\n{rest.lstrip()}" if rest else f"\n\n{outro}"
    else:
        # Unknown content after marker — still ensure outro is present once.
        if "**Live stats only**" in head:
            new_suffix = suffix
        else:
            new_suffix = f"\n\n{outro}\n{suffix_lstrip}"

    updated = prefix + new_suffix
    if not updated.endswith("\n"):
        updated += "\n"
    return updated, updated != readme


def update_readme_benchmark_section(
    master: Dict[str, Any],
    *,
    readme_path: Optional[Path] = None,
) -> bool:
    """
    Splice auto-generated benchmark stats into README.md between marker comments.

    Targets the top-of-file ``## Collaborative benchmark results`` section
    (after the project intro). If markers are missing, they are created there
    before merging. Leaderboard image is kept above ``## Project layout``.
    """
    path = readme_path or README_PATH
    if not path.is_file():
        _log_warning(f"README not found — skipping benchmark section update ({path})")
        return False

    try:
        readme = path.read_text(encoding="utf-8")
    except OSError as exc:
        _log_warning(f"failed to read README for benchmark section update: {exc}")
        return False

    readme, markers_added = ensure_readme_benchmark_markers(readme)
    if not _readme_has_benchmark_markers(readme):
        _log_warning(
            "README missing benchmark-master markers — add "
            f"{README_BENCHMARK_START} / {README_BENCHMARK_END} under "
            f"{README_BENCHMARK_HEADING!r} to enable auto-update"
        )
        return False

    from ramigpt.benchmark.leaderboard_export import ensure_readme_leaderboard_image

    readme, image_added = ensure_readme_leaderboard_image(readme)
    readme, outro_added = ensure_readme_benchmark_outro(readme)

    block = (
        f"{README_BENCHMARK_START}\n"
        f"{format_master_markdown(master, include_overall=False)}\n"
        f"{README_BENCHMARK_END}"
    )
    pattern = re.compile(
        re.escape(README_BENCHMARK_START) + r".*?" + re.escape(README_BENCHMARK_END),
        re.DOTALL,
    )
    updated = pattern.sub(block, readme, count=1)
    if updated == readme and not markers_added and not image_added and not outro_added:
        _log_warning("README benchmark section unchanged")
        return False

    try:
        path.write_text(updated, encoding="utf-8")
    except OSError as exc:
        _log_warning(f"failed to write README benchmark section: {exc}")
        return False

    _log_info(
        f"README benchmark section updated → {path}"
        + (" (markers ensured)" if markers_added else "")
    )
    return True


def _benchmark_md_has_markers(text: str) -> bool:
    return BENCHMARK_MD_START in text and BENCHMARK_MD_END in text


def _normalize_benchmark_md_heading(text: str) -> Tuple[str, bool]:
    """Rename legacy ``Collaborative scenario results`` heading if present."""
    if _LEGACY_BENCHMARK_MD_HEADING not in text:
        return text, False
    updated = re.sub(
        rf"(?m)^{re.escape(_LEGACY_BENCHMARK_MD_HEADING)}\s*$",
        BENCHMARK_MD_HEADING,
        text,
        count=1,
    )
    legacy_intro = (
        "Per-scenario stats (profile · role · target · tools), rebuilt from the same "
        "live master as the summary tables in [`README.md`](README.md). "
        "Full JSON: [`data/benchmark/results/master.json`](data/benchmark/results/master.json)."
    )
    if legacy_intro in updated:
        updated = updated.replace(legacy_intro, BENCHMARK_MD_SECTION_INTRO.rstrip("\n"), 1)
    return updated, updated != text


def ensure_benchmark_md_markers(text: str) -> Tuple[str, bool]:
    """
    Ensure ``benchmark.md`` has the collaborative results heading + markers.

    Returns ``(text, changed)``.
    """
    text, heading_changed = _normalize_benchmark_md_heading(text)
    if _benchmark_md_has_markers(text):
        return text, heading_changed

    heading_match = re.search(
        rf"(?m)^{re.escape(BENCHMARK_MD_HEADING)}\s*$",
        text,
    )
    if heading_match:
        after_heading = text[heading_match.end() :]
        end_match = re.search(r"(?m)^(?:##\s|---\s*$)", after_heading)
        if end_match:
            insert_at = heading_match.end() + end_match.start()
            prefix = text[:insert_at].rstrip("\n")
            suffix = text[insert_at:].lstrip("\n")
            markers = f"{BENCHMARK_MD_START}\n{BENCHMARK_MD_END}"
            return f"{prefix}\n\n{markers}\n\n{suffix}", True
        prefix = text.rstrip("\n")
        markers = f"{BENCHMARK_MD_START}\n{BENCHMARK_MD_END}"
        return f"{prefix}\n\n{markers}\n", True

    section = (
        f"\n\n{BENCHMARK_MD_HEADING}\n\n"
        f"{BENCHMARK_MD_SECTION_INTRO}\n"
        f"{BENCHMARK_MD_START}\n"
        f"{BENCHMARK_MD_END}\n"
    )
    _log_info(
        f"appending {BENCHMARK_MD_HEADING!r} with "
        f"{BENCHMARK_MD_START}/{BENCHMARK_MD_END} to benchmark.md"
    )
    return text.rstrip("\n") + section, True


ensure_benchmark_md_scenario_markers = ensure_benchmark_md_markers


def update_benchmark_md_section(
    master: Dict[str, Any],
    *,
    benchmark_md_path: Optional[Path] = None,
) -> bool:
    """Splice full collaborative stats (incl. scenarios) into ``benchmark.md``."""
    path = benchmark_md_path or BENCHMARK_MD_PATH
    if not path.is_file():
        _log_warning(f"benchmark.md not found — skipping collaborative update ({path})")
        return False

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        _log_warning(f"failed to read benchmark.md for collaborative update: {exc}")
        return False

    text, markers_added = ensure_benchmark_md_markers(text)
    if not _benchmark_md_has_markers(text):
        _log_warning(
            "benchmark.md missing collaborative markers — add "
            f"{BENCHMARK_MD_START} / {BENCHMARK_MD_END} under "
            f"{BENCHMARK_MD_HEADING!r} to enable auto-update"
        )
        return False

    block = (
        f"{BENCHMARK_MD_START}\n"
        f"{format_master_markdown(master, include_scenarios=True)}\n"
        f"{BENCHMARK_MD_END}"
    )
    pattern = re.compile(
        re.escape(BENCHMARK_MD_START) + r".*?" + re.escape(BENCHMARK_MD_END),
        re.DOTALL,
    )
    updated = pattern.sub(block, text, count=1)
    if updated == text and not markers_added:
        _log_warning("benchmark.md collaborative section unchanged")
        return False

    try:
        path.write_text(updated, encoding="utf-8")
    except OSError as exc:
        _log_warning(f"failed to write benchmark.md collaborative section: {exc}")
        return False

    _log_info(
        f"benchmark.md collaborative section updated → {path}"
        + (" (markers ensured)" if markers_added else "")
    )
    return True


update_benchmark_md_scenarios_section = update_benchmark_md_section


def write_master_results(
    master: Dict[str, Any],
    *,
    results_dir: Optional[Path] = None,
    update_readme: Optional[bool] = None,
) -> Path:
    """Persist master.json and master_summary.txt."""
    ensure_runtime_dirs()
    root = results_dir or BENCHMARK_RESULTS_DIR
    root.mkdir(parents=True, exist_ok=True)

    json_path = root / MASTER_JSON_NAME
    json_path.write_text(
        json.dumps(master, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    summary_path = root / MASTER_SUMMARY_NAME
    summary_path.write_text(format_master_summary(master), encoding="utf-8")
    should_update_docs = update_readme
    if should_update_docs is None:
        # Only auto-update project docs when writing the real live results
        # dir (compare against paths.BENCHMARK_RESULTS_DIR so tests that patch
        # this module's BENCHMARK_RESULTS_DIR cannot clobber README.md /
        # benchmark.md).
        from ramigpt.paths import BENCHMARK_RESULTS_DIR as live_results_dir

        should_update_docs = root.resolve() == live_results_dir.resolve()
    if should_update_docs:
        try:
            from ramigpt.benchmark.results import write_leaderboard_exports

            write_leaderboard_exports(master, results_dir=root)
        except Exception as exc:  # noqa: BLE001
            _log_warning(f"failed to write leaderboard HTML/PNG exports: {exc}")
        update_readme_benchmark_section(master)
        update_benchmark_md_scenarios_section(master)
    _log_info(
        f"master updated → {json_path} "
        f"(runs={master.get('source_runs_deduped')}, "
        f"scenarios={len((master.get('aggregate') or {}).get('by_scenario') or {})})"
    )
    return json_path


def update_master_results(*, results_dir: Optional[Path] = None) -> Path:
    """Rebuild and write the collaborative master file from all result.json sources."""
    master = build_master_document(results_dir)
    return write_master_results(master, results_dir=results_dir)


def reset_benchmark_results(*, results_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Remove all persisted benchmark results and rebuild an empty master + README section."""
    from ramigpt.benchmark.results import clear_benchmark_results

    root = results_dir or BENCHMARK_RESULTS_DIR
    removed = clear_benchmark_results(results_dir=root)
    path = update_master_results(results_dir=root)
    master = build_master_document(root)
    return {
        "removed": removed,
        "master_path": str(path),
        "runs": master.get("source_runs_deduped", 0),
    }


LEADERBOARD_DEFAULT_LIMIT = 6
LEADERBOARD_METRIC_VIEWS = (
    "got_root_count",
    "got_root_rate",
    "tokens_to_root",
)


def _target_family_lookup() -> Dict[str, str]:
    from ramigpt.benchmark.targets import TARGETS

    return {t.id: t.family for t in TARGETS}


def _catalog_target_count() -> int:
    from ramigpt.benchmark.targets import TARGETS

    return len(TARGETS)


def _profile_scenario_key(row: Dict[str, Any]) -> str:
    return f"{row.get('model') or ''}|{row.get('hardware_key') or ''}"


def _norm_scores_higher_better(values: List[Optional[float]]) -> List[Optional[float]]:
    present = [v for v in values if v is not None]
    if not present:
        return [None for _ in values]
    lo, hi = min(present), max(present)
    if hi == lo:
        return [100.0 if v is not None else None for v in values]
    return [None if v is None else round(100.0 * (v - lo) / (hi - lo), 1) for v in values]


def _norm_scores_lower_better(values: List[Optional[float]]) -> List[Optional[float]]:
    present = [v for v in values if v is not None and v > 0]
    if not present:
        return [None for _ in values]
    lo, hi = min(present), max(present)
    if hi == lo:
        return [100.0 if (v is not None and v > 0) else None for v in values]
    out: List[Optional[float]] = []
    for v in values:
        if v is None or v <= 0:
            out.append(None)
        else:
            out.append(round(100.0 * (hi - v) / (hi - lo), 1))
    return out


def _leaderboard_sort_rows(
    rows: List[Dict[str, Any]],
    *,
    metric: str = "got_root_count",
) -> List[Dict[str, Any]]:
    metric = (metric or "got_root_count").strip()
    if metric == "got_root_rate":
        return sorted(
            rows,
            key=lambda r: (
                r.get("got_root_rate") is None,
                -(r.get("got_root_rate") or 0),
                -(r.get("got_root_count") or 0),
                -(r.get("attempted") or 0),
                str(r.get("profile_label") or ""),
            ),
        )
    if metric == "tokens_to_root":
        return sorted(
            rows,
            key=lambda r: (
                r.get("usable_mean_tokens_to_root") is None,
                r.get("usable_mean_tokens_to_root")
                if r.get("usable_mean_tokens_to_root") is not None
                else 0,
                -(r.get("got_root_count") or 0),
                str(r.get("profile_label") or ""),
            ),
        )
    # Default: most resolved
    return sorted(
        rows,
        key=lambda r: (
            -(r.get("got_root_count") or 0),
            r.get("got_root_rate") is None,
            -(r.get("got_root_rate") or 0),
            -(r.get("attempted") or 0),
            str(r.get("profile_label") or ""),
        ),
    )


def _enrich_leaderboard_row(row: Dict[str, Any], *, rank: int) -> Dict[str, Any]:
    attempted = int(row.get("attempted") or 0)
    got_root = int(row.get("got_root_count") or 0)
    known = int(row.get("got_root_known") or 0)
    if known <= 0 and row.get("got_root_rate") is not None and attempted:
        # Older master.json may lack got_root_known; infer from rate when possible.
        known = attempted
    unresolved = max(known - got_root, 0) if known else max(attempted - got_root, 0)
    return {
        **row,
        "rank": rank,
        "unresolved_count": unresolved,
        "score": row.get("got_root_rate"),
        "score_percent": (
            None
            if row.get("got_root_rate") is None
            else round(float(row["got_root_rate"]) * 100.0, 1)
        ),
    }


def _family_heatmap_for_top(
    scenarios: List[Dict[str, Any]],
    top_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    families = _target_family_lookup()
    top_keys = {
        f"{r.get('model_key_name')}|{r.get('hardware_key')}": r.get("profile_label")
        for r in top_rows
    }
    # family -> profile_key -> {got_root, known}
    buckets: Dict[str, Dict[str, Dict[str, int]]] = {}
    family_order: List[str] = []
    for sc in scenarios:
        pk = _profile_scenario_key(sc)
        if pk not in top_keys:
            continue
        family = families.get(str(sc.get("target_id") or ""), "unknown")
        if family not in family_order:
            family_order.append(family)
        cell = buckets.setdefault(family, {}).setdefault(pk, {"got_root": 0, "known": 0})
        cell["got_root"] += int(sc.get("got_root_count") or 0)
        # Approximate known outcomes from observations with a rate when available.
        rate = sc.get("got_root_rate")
        count = int(sc.get("got_root_count") or 0)
        if rate and rate > 0:
            cell["known"] += max(int(round(count / rate)), count)
        else:
            cell["known"] += max(int(sc.get("attempted") or sc.get("observations") or 0), count)

    family_order = sorted(family_order)
    profiles = [
        {
            "profile_key": f"{r.get('model_key_name')}|{r.get('hardware_key')}",
            "profile_label": r.get("profile_label"),
            "rank": r.get("rank"),
        }
        for r in top_rows
    ]
    cells: List[Dict[str, Any]] = []
    for family in family_order:
        for p in profiles:
            pk = p["profile_key"]
            data = (buckets.get(family) or {}).get(pk) or {"got_root": 0, "known": 0}
            known = data["known"]
            got = data["got_root"]
            cells.append(
                {
                    "family": family,
                    "profile_key": pk,
                    "profile_label": p["profile_label"],
                    "got_root_count": got,
                    "got_root_known": known,
                    "got_root_rate": _rate(got, known) if known else None,
                }
            )
    return {"families": family_order, "profiles": profiles, "cells": cells}


def _trend_from_runs(runs_index: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Daily then cumulative pass/attempt trend from run summaries."""
    by_day: Dict[str, Dict[str, int]] = {}
    for run in runs_index:
        finished = _parse_ts(run.get("finished_at")) or _parse_ts(run.get("started_at"))
        if finished is None:
            continue
        day = finished.date().isoformat()
        summary = run.get("summary") if isinstance(run.get("summary"), dict) else {}
        bucket = by_day.setdefault(day, {"runs": 0, "attempted": 0, "passed": 0})
        bucket["runs"] += 1
        bucket["attempted"] += int(summary.get("attempted") or 0)
        bucket["passed"] += int(summary.get("passed") or 0)

    points: List[Dict[str, Any]] = []
    cum_attempted = 0
    cum_passed = 0
    cum_runs = 0
    for day in sorted(by_day.keys()):
        bucket = by_day[day]
        cum_attempted += bucket["attempted"]
        cum_passed += bucket["passed"]
        cum_runs += bucket["runs"]
        points.append(
            {
                "date": day,
                "runs": bucket["runs"],
                "attempted": bucket["attempted"],
                "passed": bucket["passed"],
                "pass_rate": _rate(bucket["passed"], bucket["attempted"]),
                "cumulative_runs": cum_runs,
                "cumulative_attempted": cum_attempted,
                "cumulative_passed": cum_passed,
                "cumulative_pass_rate": _rate(cum_passed, cum_attempted),
            }
        )
    return points


def _tools_impact_from_scenarios(scenarios: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    buckets: Dict[str, Dict[str, Any]] = {}
    for sc in scenarios:
        tools = list(sc.get("tools") or [])
        label = ", ".join(tools) if tools else "none"
        key = label
        bucket = buckets.setdefault(
            key,
            {"tools": tools, "tools_label": label, "got_root": 0, "known": 0, "scenarios": 0},
        )
        bucket["scenarios"] += 1
        got = int(sc.get("got_root_count") or 0)
        bucket["got_root"] += got
        rate = sc.get("got_root_rate")
        if rate and rate > 0:
            bucket["known"] += max(int(round(got / rate)), got)
        else:
            bucket["known"] += max(int(sc.get("attempted") or sc.get("observations") or 0), got)
    rows = []
    for bucket in buckets.values():
        rows.append(
            {
                "tools": bucket["tools"],
                "tools_label": bucket["tools_label"],
                "scenarios": bucket["scenarios"],
                "got_root_count": bucket["got_root"],
                "got_root_known": bucket["known"],
                "got_root_rate": _rate(bucket["got_root"], bucket["known"]),
            }
        )
    rows.sort(
        key=lambda r: (
            r.get("got_root_rate") is None,
            -(r.get("got_root_rate") or 0),
            -(r.get("got_root_count") or 0),
        )
    )
    return rows


def _hardware_comparison(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_model: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        by_model.setdefault(str(row.get("model_key_name") or ""), []).append(row)
    out: List[Dict[str, Any]] = []
    for model_key, group in sorted(by_model.items()):
        if len(group) < 2:
            continue
        for row in group:
            out.append(
                {
                    "model_key_name": model_key,
                    "profile_label": row.get("profile_label"),
                    "hardware_key": row.get("hardware_key"),
                    "hardware_label": row.get("hardware_label"),
                    "got_root_count": row.get("got_root_count", 0),
                    "got_root_rate": row.get("got_root_rate"),
                    "mean_elapsed_to_root": row.get("mean_elapsed_to_root"),
                    "usable_mean_tokens_to_root": row.get("usable_mean_tokens_to_root"),
                    "runs": row.get("runs", 0),
                }
            )
    return out


def _coverage_for_top(
    scenarios: List[Dict[str, Any]],
    top_rows: List[Dict[str, Any]],
    catalog_size: int,
) -> List[Dict[str, Any]]:
    targets_by_profile: Dict[str, set] = {}
    for sc in scenarios:
        pk = _profile_scenario_key(sc)
        targets_by_profile.setdefault(pk, set()).add(str(sc.get("target_id") or ""))
    out = []
    for row in top_rows:
        pk = f"{row.get('model_key_name')}|{row.get('hardware_key')}"
        attempted_targets = len(targets_by_profile.get(pk) or set())
        out.append(
            {
                "profile_key": row.get("profile_key"),
                "profile_label": row.get("profile_label"),
                "rank": row.get("rank"),
                "targets_attempted": attempted_targets,
                "catalog_size": catalog_size,
                "coverage_rate": _rate(attempted_targets, catalog_size),
            }
        )
    return out


def _radar_for_top(top_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    success = [r.get("got_root_rate") for r in top_rows]
    speed = [r.get("mean_elapsed_to_root") for r in top_rows]
    tokens = [r.get("usable_mean_tokens_to_root") for r in top_rows]
    requests = [r.get("mean_ai_requests_to_root") for r in top_rows]
    success_n = _norm_scores_higher_better(success)
    speed_n = _norm_scores_lower_better(speed)
    tokens_n = _norm_scores_lower_better(tokens)
    requests_n = _norm_scores_lower_better(requests)
    out = []
    for idx, row in enumerate(top_rows):
        out.append(
            {
                "profile_key": row.get("profile_key"),
                "profile_label": row.get("profile_label"),
                "rank": row.get("rank"),
                "axes": {
                    "success": success_n[idx],
                    "speed": speed_n[idx],
                    "token_efficiency": tokens_n[idx],
                    "request_efficiency": requests_n[idx],
                },
            }
        )
    return out


def build_leaderboard_payload(
    master: Optional[Dict[str, Any]],
    *,
    limit: int = LEADERBOARD_DEFAULT_LIMIT,
    metric: str = "got_root_count",
) -> Dict[str, Any]:
    """Compact leaderboard document for the UI (never includes by_scenario aggregates)."""
    try:
        limit_i = max(1, min(int(limit), 50))
    except (TypeError, ValueError):
        limit_i = LEADERBOARD_DEFAULT_LIMIT
    metric = (metric or "got_root_count").strip()
    if metric not in LEADERBOARD_METRIC_VIEWS:
        metric = "got_root_count"

    if not master:
        return {
            "ok": False,
            "error": "No master results yet — run a benchmark or rebuild master results",
            "limit": limit_i,
            "metric": metric,
            "updated_at": None,
            "summary": {},
            "top": [],
            "models": [],
            "charts": {},
            "methodology": {
                "score": "got_root_rate = got_root_count / outcomes where got_root is known "
                "(scoreable attempts: pass + wall-clock timeout + max_requests)",
                "resolved": "got_root_count among scoreable attempts",
                "tokens": "Zero/missing token telemetry is excluded from efficiency rankings",
            },
        }

    rankings = (master.get("rankings") or {}).get("profiles") or {}
    # Prefer fresh sort from by_got_root_count when present; else re-sort any view.
    all_rows = list(
        rankings.get("by_got_root_count")
        or rankings.get("by_got_root_rate")
        or rankings.get("by_pass_rate")
        or []
    )
    # Deduplicate by profile_key (views share the same row objects conceptually).
    seen: set[str] = set()
    unique_rows: List[Dict[str, Any]] = []
    for row in all_rows:
        pk = str(row.get("profile_key") or "")
        if pk in seen:
            continue
        seen.add(pk)
        unique_rows.append(row)

    # If master was built before ranking field extensions, enrich from aggregate.
    by_profile = ((master.get("aggregate") or {}).get("by_profile")) or {}
    enriched_all: List[Dict[str, Any]] = []
    for row in unique_rows:
        stats = by_profile.get(str(row.get("profile_key") or "")) or {}
        merged = dict(row)
        if "got_root_known" not in merged and stats:
            merged["got_root_known"] = stats.get("got_root_known", 0)
        if "mean_prompt_tokens" not in merged and stats:
            merged.update(
                {
                    k: v
                    for k, v in _stats_ranking_fields(stats).items()
                    if k not in merged or merged.get(k) is None
                }
            )
        # Ensure usable_* even when loading older ranking rows.
        if "usable_mean_tokens_to_root" not in merged:
            merged["usable_mean_tokens_to_root"] = _positive_or_none(
                merged.get("mean_tokens_to_root")
            )
        if "usable_mean_prompt_tokens" not in merged:
            merged["usable_mean_prompt_tokens"] = _positive_or_none(
                merged.get("mean_prompt_tokens")
            )
        if "usable_mean_prompt_tokens_to_root" not in merged:
            merged["usable_mean_prompt_tokens_to_root"] = _positive_or_none(
                merged.get("mean_prompt_tokens_to_root")
            )
        if "usable_tokens_per_second_to_root" not in merged:
            merged["usable_tokens_per_second_to_root"] = _positive_or_none(
                merged.get("tokens_per_second_to_root")
            )
        enriched_all.append(merged)

    sorted_rows = _leaderboard_sort_rows(enriched_all, metric=metric)
    top_raw = sorted_rows[:limit_i]
    top = [_enrich_leaderboard_row(row, rank=i + 1) for i, row in enumerate(top_raw)]
    models = [
        _enrich_leaderboard_row(row, rank=i + 1) for i, row in enumerate(sorted_rows)
    ]

    overall = (master.get("aggregate") or {}).get("overall") or {}
    catalog = master.get("catalog") or {}
    catalog_size = _catalog_target_count()
    scenarios = list((master.get("rankings") or {}).get("scenarios") or [])
    runs_index = list(master.get("runs_index") or [])

    summary = {
        "models": len(catalog.get("model_key_names") or []),
        "profiles": len(enriched_all),
        "runs": master.get("source_runs_deduped") or overall.get("runs") or 0,
        "observations": overall.get("observations", 0),
        "attempted": overall.get("attempted", 0),
        "got_root_count": overall.get("got_root_count", 0),
        "got_root_rate": overall.get("got_root_rate"),
        "catalog_targets": catalog_size,
        "roles": len(catalog.get("roles") or []),
        "tools": list(catalog.get("tools") or []),
    }

    return {
        "ok": True,
        "limit": limit_i,
        "metric": metric,
        "metric_views": list(LEADERBOARD_METRIC_VIEWS),
        "updated_at": master.get("updated_at"),
        "summary": summary,
        "top": top,
        "models": models,
        "charts": {
            "family_heatmap": _family_heatmap_for_top(scenarios, top),
            "trend": _trend_from_runs(runs_index),
            "tools_impact": _tools_impact_from_scenarios(scenarios),
            "hardware_comparison": _hardware_comparison(enriched_all),
            "coverage": _coverage_for_top(scenarios, top, catalog_size),
            "radar": _radar_for_top(top),
        },
        "methodology": {
            "score": "got_root_rate = got_root_count / outcomes where got_root is known "
            "(scoreable attempts: pass + wall-clock timeout + max_requests)",
            "resolved": "got_root_count among scoreable attempts",
            "tokens": "Zero/missing token telemetry is excluded from efficiency rankings",
            "trend": "Daily run summaries; cumulative passed/attempted from collab sheets",
        },
    }


def load_leaderboard_payload(
    *,
    results_dir: Optional[Path] = None,
    limit: int = LEADERBOARD_DEFAULT_LIMIT,
    metric: str = "got_root_count",
) -> Dict[str, Any]:
    """Load master.json and return a compact leaderboard payload."""
    return build_leaderboard_payload(
        load_master_results(results_dir=results_dir),
        limit=limit,
        metric=metric,
    )


def load_master_results(*, results_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Load master.json if it exists."""
    root = results_dir or BENCHMARK_RESULTS_DIR
    path = root / MASTER_JSON_NAME
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _log_warning(f"failed to read master results: {exc}")
        return None
