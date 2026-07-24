#!/usr/bin/env python3
"""Update docker/benchmark/beroot-coverage.md from verification JSON files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from ramigpt.benchmark.targets import TARGETS, get_target


ROW_RE = re.compile(
    r"^\| `(?P<id>[^`]+)` \| (?P<port>\d+) \| (?P<family>[^|]+) \| "
    r"\*\*(?P<verdict>Yes|Partial|No)\*\* \| (?P<note>.*?) \|$",
    re.MULTILINE,
)


def _format_note(row: dict, *, host: str, verified_date: str) -> str:
    check = (row.get("check") or "").strip()
    note = (row.get("note") or "").strip()
    if row["id"].startswith("cred-"):
        prefix = f"credential_leaks (verified {verified_date} on {host})"
    elif check:
        prefix = f"{check} (verified {verified_date} on {host})"
    else:
        prefix = f"verified {verified_date} on {host}"
    if note and note not in prefix:
        return f"{prefix} — {note}"
    return prefix


def _load_results(*paths: Path) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for path in paths:
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        host = data.get("host", "?")
        verified_at = (data.get("verified_at") or "")[:10] or str(date.today())
        for row in data.get("results", []):
            verdict = row.get("verdict", "No")
            if verdict == "Partial":
                verdict = "No"
            elif verdict == "Error":
                verdict = "No"
            merged[row["id"]] = {
                **row,
                "verdict": verdict,
                "_host": host,
                "_date": verified_at,
            }
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--coverage",
        default="docker/benchmark/beroot-coverage.md",
        help="Coverage markdown path",
    )
    parser.add_argument(
        "--verify",
        action="append",
        default=[
            "docker/benchmark/beroot-cred-verify.json",
            "docker/benchmark/beroot-verify.json",
        ],
        help="Verification JSON (repeatable)",
    )
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[2]
    coverage_path = repo / args.coverage
    text = coverage_path.read_text(encoding="utf-8")
    results = _load_results(*(repo / p for p in args.verify))

    counts = {"Yes": 0, "No": 0}

    def replace_row(match: re.Match[str]) -> str:
        tid = match.group("id")
        if tid not in results:
            verdict = match.group("verdict")
            if verdict == "Partial":
                verdict = "No"
            counts[verdict] = counts.get(verdict, 0) + 1
            note = match.group("note")
            if match.group("verdict") == "Partial":
                note = f"reclassified from Partial → No — {note}"
            return (
                f"| `{tid}` | {match.group('port')} | {match.group('family').strip()} | "
                f"**{verdict}** | {note} |"
            )
        row = results[tid]
        verdict = row.get("verdict", "No")
        if verdict not in ("Yes", "No"):
            verdict = "No"
        counts[verdict] += 1
        try:
            target = get_target(tid)
            family = target.family
        except KeyError:
            family = match.group("family").strip()
        port = row.get("port", match.group("port"))
        note = _format_note(row, host=row.get("_host", "?"), verified_date=row.get("_date", ""))
        note = note.replace("|", "\\|")
        return f"| `{tid}` | {port} | {family} | **{verdict}** | {note} |"

    updated = ROW_RE.sub(replace_row, text)
    total = sum(counts.values())
    summary_block = (
        "| Verdict | Count |\n"
        "|---------|------:|\n"
        f"| Yes | {counts['Yes']} |\n"
        f"| No | {counts['No']} |\n"
        f"| **Total** | **{total}** |"
    )
    updated = re.sub(
        r"\| Verdict \| Count \|\n\|---------\|------:\|\n(?:\| [^\n]+\n)+",
        summary_block + "\n",
        updated,
        count=1,
    )

    # Legend: drop Partial.
    updated = re.sub(
        r"\| \*\*Partial\*\* \|[^\n]+\n",
        "",
        updated,
        count=1,
    )

    hosts = sorted({row.get("_host", "?") for row in results.values()})
    cred_yes = sum(
        1 for r in results.values() if r["id"].startswith("cred-") and r.get("verdict") == "Yes"
    )
    cred_no = sum(
        1 for r in results.values() if r["id"].startswith("cred-") and r.get("verdict") == "No"
    )
    noncred = [r for r in results.values() if not r["id"].startswith("cred-")]
    if noncred:
        nc_summary: dict[str, int] = {}
        for row in noncred:
            v = row.get("verdict", "No")
            nc_summary[v] = nc_summary.get(v, 0) + 1
        banner = (
            f"**Remote verification** on `{hosts[0] if hosts else '?'}` "
            f"(cred: {cred_yes} Yes, {cred_no} No; "
            f"other: {nc_summary.get('Yes', 0)} Yes, {nc_summary.get('No', 0)} No) — see "
            f"[`beroot-cred-verify.json`](beroot-cred-verify.json) and "
            f"[`beroot-verify.json`](beroot-verify.json)."
        )
    else:
        banner = (
            f"**cred-\\* labs verified remotely** on `{hosts[0] if hosts else '?'}` "
            f"({cred_yes} Yes, {cred_no} No) — see [`beroot-cred-verify.json`](beroot-cred-verify.json)."
        )

    if "**Remote verification**" in updated or "**cred-\\* labs verified remotely**" in updated:
        updated = re.sub(
            r"\*\*(?:Remote verification|cred-\\\* labs verified remotely)\*\*[^\n]+\n",
            banner + "\n\n",
            updated,
            count=1,
        )
    else:
        updated = updated.replace(
            "run as `lowpriv` (as in benchmark / `ramigpt/web/tools/beroot.py`).\n",
            "run as `lowpriv` (as in benchmark / `ramigpt/web/tools/beroot.py`).\n\n" + banner + "\n",
        )

    coverage_path.write_text(updated, encoding="utf-8")
    print("Updated", coverage_path)
    print("Summary:", counts, "total", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
