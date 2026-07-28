#!/usr/bin/env python3
"""Run full BeRoot against every non-cred benchmark lab and classify output."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from pwn import context, ssh

from ramigpt.benchmark.beroot_classify import classify_beroot_output
from ramigpt.benchmark.targets import BENCH_PASSWORD, BENCH_USERNAME, TARGETS
from ramigpt.web.tools.beroot import upload_and_run_beroot

context.log_level = "error"


def _targets(*, skip_creds: bool, family: str | None, ids: list[str] | None):
    selected = list(TARGETS)
    if skip_creds:
        selected = [t for t in selected if not t.id.startswith("cred-")]
    if family:
        selected = [t for t in selected if t.family == family]
    if ids:
        wanted = set(ids)
        selected = [t for t in selected if t.id in wanted]
    return sorted(selected, key=lambda t: t.id)


def _load_existing(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {row["id"]: row for row in data.get("results", [])}


def _merge_results(existing: dict[str, dict], updates: list[dict]) -> list[dict]:
    merged = dict(existing)
    for row in updates:
        merged[row["id"]] = row
    return [merged[key] for key in sorted(merged)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="Benchmark lab IP/host")
    parser.add_argument(
        "--output",
        default="docker/benchmark/beroot-verify.json",
        help="JSON results path (relative to repo root)",
    )
    parser.add_argument("--skip-creds", action="store_true", default=True)
    parser.add_argument("--include-creds", action="store_true")
    parser.add_argument("--family", default="", help="Filter by target family")
    parser.add_argument("--ids", nargs="*", help="Only these target ids")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true", help="Skip ids already in output")
    parser.add_argument("--force", action="store_true", help="Re-scan even when resuming")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    skip_creds = args.skip_creds and not args.include_creds
    repo = Path(__file__).resolve().parents[2]
    out_path = repo / args.output
    existing = _load_existing(out_path) if (args.resume or args.ids) else {}

    targets = _targets(skip_creds=skip_creds, family=args.family or None, ids=args.ids)
    if args.limit:
        targets = targets[: args.limit]

    results: list[dict] = []
    scanned: list[dict] = []
    for idx, target in enumerate(targets, start=1):
        if args.resume and not args.force and target.id in existing:
            print(f"[{idx}/{len(targets)}] {target.id} -> resume {existing[target.id].get('verdict')}")
            continue

        print(
            f"[{idx}/{len(targets)}] {target.id} ({target.family}) @ {args.host}:{target.port} ...",
            flush=True,
        )
        entry = {
            "id": target.id,
            "port": target.port,
            "host": args.host,
            "family": target.family,
        }
        conn = None
        try:
            conn = ssh(
                user=BENCH_USERNAME,
                host=args.host,
                port=target.port,
                password=BENCH_PASSWORD,
                timeout=15,
                ignore_config=True,
            )
            output = upload_and_run_beroot(
                conn,
                password=BENCH_PASSWORD,
                timeout=args.timeout,
            )
            cls = classify_beroot_output(target, output)
            entry.update(
                {
                    "verdict": cls.verdict,
                    "check": cls.check,
                    "note": cls.note,
                    "output_chars": len(output),
                }
            )
            print(f"  -> {cls.verdict}: {cls.note[:100]}")
        except Exception as exc:  # noqa: BLE001
            note = str(exc)[:200]
            if target.id == "rbash-escape" and "restricted" in note.lower():
                entry.update(
                    {
                        "verdict": "No",
                        "check": "",
                        "note": "no restricted-shell check; BeRoot upload blocked in rbash",
                        "output_chars": 0,
                    }
                )
                print("  -> No: rbash blocks BeRoot upload")
            else:
                entry.update(
                    {
                        "verdict": "Error",
                        "check": "",
                        "note": note,
                        "output_chars": 0,
                    }
                )
                print(f"  -> Error: {entry['note'][:100]}")
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
        scanned.append(entry)

        results = _merge_results(existing, scanned)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        summary: dict[str, int] = {}
        for row in results:
            summary[row["verdict"]] = summary.get(row["verdict"], 0) + 1
        out_path.write_text(
            json.dumps(
                {
                    "verified_at": datetime.now(timezone.utc).isoformat(),
                    "host": args.host,
                    "target_count": len(results),
                    "summary": summary,
                    "results": results,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    if not scanned and args.resume and existing:
        results = _merge_results(existing, [])
    else:
        results = _merge_results(existing, scanned)

    summary = {}
    for row in results:
        summary[row["verdict"]] = summary.get(row["verdict"], 0) + 1
    print("\nSummary:", summary)
    print("Wrote", out_path)
    return 0 if summary.get("Error", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
