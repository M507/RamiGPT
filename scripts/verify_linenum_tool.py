#!/usr/bin/env python3
"""Live verification: upload and run LinEnum on a benchmark SSH target."""

from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("PWNLIB_NOTERM", "1")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pwn import context, ssh  # noqa: E402

context.log_level = "error"

from ramigpt.paths import LINENUM_SCRIPT, LINENUM_DOWNLOADS_DIR  # noqa: E402
from ramigpt.tools.linenum import sanitize_linenum_for_prompt, upload_and_run_linenum  # noqa: E402
from ramigpt.web.app import _sh_single_quote, _ssh_run_or_shell  # noqa: E402

HOST = os.environ.get("BENCH_HOST", "10.10.1.109")
PORT = int(os.environ.get("BENCH_PORT", "2211"))
USER = os.environ.get("BENCH_USER", "lowpriv")
PASSWORD = os.environ.get("BENCH_PASS", "password")
TIMEOUT = int(os.environ.get("LINENUM_TIMEOUT", "180"))


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    if not LINENUM_SCRIPT.is_file():
        _fail(f"LinEnum script missing at {LINENUM_SCRIPT}")

    print(f"=== LinEnum live verify ===")
    print(f"target={HOST}:{PORT} user={USER}")
    print(f"script={LINENUM_SCRIPT} ({LINENUM_SCRIPT.stat().st_size} bytes)")

    conn = ssh(host=HOST, port=PORT, user=USER, password=PASSWORD, ignore_config=True)
    try:
        started = time.monotonic()
        raw = upload_and_run_linenum(
            conn,
            password=PASSWORD,
            sh_quote=_sh_single_quote,
            ssh_run=_ssh_run_or_shell,
            slog=None,
            timeout=TIMEOUT,
        )
        elapsed = round(time.monotonic() - started, 1)
    finally:
        conn.close()

    if len(raw) < 500:
        _fail(f"output too short ({len(raw)} chars): {raw[:300]!r}")

    cleaned = sanitize_linenum_for_prompt(raw)
    if len(cleaned) < 400:
        _fail(f"sanitized output too short ({len(cleaned)} chars)")

    markers = [
        "Local Linux Enumeration",
        "LinEnum",
        "Scan started at",
    ]
    missing = [m for m in markers if m not in raw and m not in cleaned]
    if missing:
        _fail(f"expected markers missing from output: {missing}")

    if "\x1b[" in cleaned:
        _fail("sanitized output still contains ANSI escapes")

    LINENUM_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = LINENUM_DOWNLOADS_DIR / "verify_linenum_smoke.txt"
    out_path.write_text(cleaned, encoding="utf-8")

    print(f"OK: scan finished in {elapsed}s")
    print(f"OK: raw={len(raw)} chars sanitized={len(cleaned)} chars")
    print(f"OK: saved {out_path}")
    print("--- preview (first 1200 chars) ---")
    print(cleaned[:1200])
    print("--- end preview ---")


if __name__ == "__main__":
    main()
