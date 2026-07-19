#!/usr/bin/env python3
"""Live verification: upload and run LinPEAS on a benchmark SSH target."""

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

from ramigpt.paths import LINPEAS_DOWNLOADS_DIR, LINPEAS_SCRIPT  # noqa: E402
from ramigpt.tools.linpeas import sanitize_linpeas_for_prompt, upload_and_run_linpeas  # noqa: E402
from ramigpt.web.app import _sh_single_quote, _ssh_run_or_shell  # noqa: E402

HOST = os.environ.get("BENCH_HOST", "10.10.1.109")
PORT = int(os.environ.get("BENCH_PORT", "2211"))
USER = os.environ.get("BENCH_USER", "lowpriv")
PASSWORD = os.environ.get("BENCH_PASS", "password")
TIMEOUT = int(os.environ.get("LINPEAS_TIMEOUT", "600"))


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    if not LINPEAS_SCRIPT.is_file():
        _fail(f"LinPEAS script missing at {LINPEAS_SCRIPT}")

    print("=== LinPEAS live verify ===")
    print(f"target={HOST}:{PORT} user={USER}")
    print(f"script={LINPEAS_SCRIPT} ({LINPEAS_SCRIPT.stat().st_size} bytes)")

    conn = ssh(host=HOST, port=PORT, user=USER, password=PASSWORD, ignore_config=True)
    try:
        started = time.monotonic()
        raw = upload_and_run_linpeas(
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

    if len(raw) < 1000:
        _fail(f"output too short ({len(raw)} chars): {raw[:300]!r}")

    cleaned = sanitize_linpeas_for_prompt(raw)
    if len(cleaned) < 800:
        _fail(f"sanitized output too short ({len(cleaned)} chars)")

    markers = ["LinPEAS", "Basic information", "Sudo version"]
    missing = [m for m in markers if m not in raw and m not in cleaned]
    if missing:
        _fail(f"expected markers missing from output: {missing}")

    if "NOPASSWD" not in raw and "NOPASSWD" not in cleaned:
        _fail("expected sudo/NOPASSWD finding on sudo-vim benchmark target")

    if "\x1b[" in cleaned:
        _fail("sanitized output still contains ANSI escapes")

    LINPEAS_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = LINPEAS_DOWNLOADS_DIR / "verify_linpeas_smoke.txt"
    out_path.write_text(raw, encoding="utf-8")

    print(f"OK: scan finished in {elapsed}s")
    print(f"OK: raw={len(raw)} chars sanitized={len(cleaned)} chars")
    print(f"OK: saved {out_path}")
    print("--- preview (first 1200 chars) ---")
    print(cleaned[:1200])
    print("--- end preview ---")


if __name__ == "__main__":
    main()
