#!/usr/bin/env python3
"""Run BeRoot credential_leaks against every cred-* benchmark lab over SSH."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from pwn import ssh, context

from ramigpt.benchmark.targets import BENCH_PASSWORD, BENCH_USERNAME, TARGETS
from ramigpt.web.shell.ssh_remote import _sh_single_quote, _ssh_run_or_shell
from ramigpt.web.tools.beroot import _upload_beroot_tree

context.log_level = "error"


def _cred_targets():
    return sorted(
        (t for t in TARGETS if t.id.startswith("cred-")),
        key=lambda t: t.id,
    )


def _run_cred_scan(conn, *, timeout: int = 90) -> str:
    remote_linux = _upload_beroot_tree(conn)
    linux_q = _sh_single_quote(remote_linux)
    remote_cmd = (
        f"cd {linux_q} && python3 - <<'PY'\n"
        "from beroot.modules.users import Users\n"
        "from beroot.modules.credentials import scan_credential_leaks\n"
        "hits = scan_credential_leaks(Users().current)\n"
        "print('\\n'.join(hits) if hits else '')\n"
        "PY"
    )
    buf = _ssh_run_or_shell(conn, remote_cmd, timeout=timeout)
    return (buf or b"").decode("utf-8", errors="replace").strip()


def _classify(target_id: str, output: str, error: str | None) -> tuple[str, str]:
    if error:
        return "Error", error[:160]
    if not output:
        return "No", "credential_leaks returned empty"
    # Heuristic miss: only flags unrelated tmp keys without lab-specific path
    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    if len(lines) == 1 and "/tmp/" in lines[0] and "root_id_rsa" in lines[0]:
        return "No", output.replace("\n", " | ")[:160]
    return "Yes", output.replace("\n", " | ")[:160]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="Benchmark lab IP/host")
    parser.add_argument(
        "--output",
        default="docker/benchmark/beroot-cred-verify.json",
        help="JSON results path (relative to repo root)",
    )
    parser.add_argument("--limit", type=int, default=0, help="Max labs (0 = all)")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[2]
    out_path = repo / args.output
    targets = _cred_targets()
    if args.limit:
        targets = targets[: args.limit]

    results = []
    for idx, target in enumerate(targets, start=1):
        print(f"[{idx}/{len(targets)}] {target.id} @ {args.host}:{target.port} ...", flush=True)
        entry = {
            "id": target.id,
            "port": target.port,
            "host": args.host,
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
            output = _run_cred_scan(conn)
            verdict, note = _classify(target.id, output, None)
            entry.update(
                {
                    "verdict": verdict,
                    "note": note,
                    "output": output,
                }
            )
            print(f"  -> {verdict}: {note[:100]}")
        except Exception as exc:  # noqa: BLE001
            verdict, note = _classify(target.id, "", str(exc))
            entry.update({"verdict": verdict, "note": note, "output": ""})
            print(f"  -> {verdict}: {note[:100]}")
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
        results.append(entry)

    summary = {}
    for row in results:
        summary[row["verdict"]] = summary.get(row["verdict"], 0) + 1

    doc = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "host": args.host,
        "target_count": len(results),
        "summary": summary,
        "results": results,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print("\nSummary:", summary)
    print("Wrote", out_path)
    return 0 if summary.get("No", 0) == 0 and summary.get("Error", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
