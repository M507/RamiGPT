"""Verify benchmark misconfig targets can actually obtain root.

Standalone:
  python3 -m ramigpt.benchmark.verify 10.10.1.109
  python3 -m ramigpt.benchmark.verify 10.10.1.109 --targets sudo-env,cap-python
  python3 -m ramigpt.benchmark.verify --write-catalog

Shell entrypoint:
  ./scripts/benchmark/verify-misconfigs.sh <host> [target_id ...]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from ramigpt.benchmark.targets import TARGETS, resolve_targets
from ramigpt.paths import PROJECT_ROOT, SCRIPTS_DIR
from ramigpt.utils import debug_logger

VERIFY_SCRIPT = SCRIPTS_DIR / "benchmark" / "verify-misconfigs.sh"
CHECKS_DIR = SCRIPTS_DIR / "benchmark" / "checks"
CATALOG_PATH = CHECKS_DIR / "catalog.tsv"

LogFn = Callable[[str], None]


@dataclass
class VerifyResult:
    target_id: str
    port: int
    expects_root: bool
    status: str  # pass | fail | flagged
    detail: str = ""
    elapsed_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.target_id,
            "port": self.port,
            "expects_root": self.expects_root,
            "status": self.status,
            "detail": self.detail,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
        }


@dataclass
class VerifyRun:
    id: str
    host: str
    phase: str = "idle"
    running: bool = False
    log_lines: List[str] = field(default_factory=list)
    results: List[VerifyResult] = field(default_factory=list)
    error: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0

    def to_public_dict(self) -> Dict[str, Any]:
        failed = [r.to_dict() for r in self.results if r.status == "fail"]
        flagged = [r.to_dict() for r in self.results if r.status == "flagged"]
        passed = [r.to_dict() for r in self.results if r.status == "pass"]
        return {
            "id": self.id,
            "host": self.host,
            "phase": self.phase,
            "running": self.running,
            "error": self.error,
            "log": "\n".join(self.log_lines[-200:]),
            "results": [r.to_dict() for r in self.results],
            "summary": {
                "pass": len(passed),
                "fail": len(failed),
                "flagged_no_root": len(flagged),
                "failed_ids": [r["id"] for r in failed],
                "flagged_ids": [r["id"] for r in flagged],
            },
            "ok": (not self.running) and (not failed) and (not self.error),
        }


_lock = threading.Lock()
_active: Optional[VerifyRun] = None


def write_catalog(path: Path = CATALOG_PATH) -> Path:
    """Write id/port/expects_root/script catalog for the bash runner."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# id\tport\texpects_root\tscript"]
    for t in TARGETS:
        expects = "1" if t.expects_root else "0"
        script = t.verify_script or f"{t.id}.sh"
        lines.append(f"{t.id}\t{t.port}\t{expects}\t{script}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def ensure_check_scripts_executable() -> None:
    for script in CHECKS_DIR.glob("*.sh"):
        script.chmod(script.stat().st_mode | 0o111)
    if VERIFY_SCRIPT.is_file():
        VERIFY_SCRIPT.chmod(VERIFY_SCRIPT.stat().st_mode | 0o111)


def get_verify_status() -> Dict[str, Any]:
    with _lock:
        if _active is None:
            return {
                "running": False,
                "phase": "idle",
                "run": None,
            }
        return {
            "running": _active.running,
            "phase": _active.phase,
            "run": _active.to_public_dict(),
        }


def _log(run: VerifyRun, message: str) -> None:
    line = message.rstrip()
    run.log_lines.append(line)
    debug_logger.info(f"[bench-verify] {line}")


def _run_one_check(
    *,
    host: str,
    target_id: str,
    port: int,
    expects_root: bool,
    user: str,
    password: str,
    timeout: int = 120,
) -> VerifyResult:
    script = CHECKS_DIR / f"{target_id}.sh"
    if not script.is_file():
        return VerifyResult(
            target_id=target_id,
            port=port,
            expects_root=expects_root,
            status="fail",
            detail=f"missing check script {script.name}",
        )
    ensure_check_scripts_executable()
    env = {
        **os.environ,
        "BENCH_HOST": host,
        "BENCH_PORT": str(port),
        "BENCH_USER": user,
        "BENCH_PASS": password,
        "BENCH_PASSWORD": password,
        "BENCH_FLAG": "FLAG{======RamiGPTi=====}",
    }
    started = time.time()
    try:
        proc = subprocess.run(
            ["bash", str(script)],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(PROJECT_ROOT),
            check=False,
        )
        out = ((proc.stdout or "") + (proc.stderr or "")).strip()
        elapsed = time.time() - started
        if not expects_root:
            if proc.returncode == 0:
                return VerifyResult(
                    target_id=target_id,
                    port=port,
                    expects_root=False,
                    status="flagged",
                    detail=out or "detect-ok, no root path",
                    elapsed_seconds=elapsed,
                )
            return VerifyResult(
                target_id=target_id,
                port=port,
                expects_root=False,
                status="fail",
                detail=out or "detect check failed",
                elapsed_seconds=elapsed,
            )
        if proc.returncode == 0:
            return VerifyResult(
                target_id=target_id,
                port=port,
                expects_root=True,
                status="pass",
                detail=out or "OK",
                elapsed_seconds=elapsed,
            )
        return VerifyResult(
            target_id=target_id,
            port=port,
            expects_root=True,
            status="fail",
            detail=out or f"exit {proc.returncode}",
            elapsed_seconds=elapsed,
        )
    except subprocess.TimeoutExpired:
        return VerifyResult(
            target_id=target_id,
            port=port,
            expects_root=expects_root,
            status="fail",
            detail=f"timeout after {timeout}s",
            elapsed_seconds=time.time() - started,
        )
    except Exception as exc:  # noqa: BLE001
        return VerifyResult(
            target_id=target_id,
            port=port,
            expects_root=expects_root,
            status="fail",
            detail=str(exc),
            elapsed_seconds=time.time() - started,
        )


def run_verify(
    host: str,
    *,
    target_ids: Optional[Sequence[str]] = None,
    user: str = "lowpriv",
    password: str = "password",
    log: Optional[LogFn] = None,
) -> Dict[str, Any]:
    """Synchronously verify targets; returns a public dict."""
    if not shutil.which("sshpass"):
        raise RuntimeError("sshpass is required on PATH to verify benchmark targets")
    write_catalog()
    ensure_check_scripts_executable()
    targets = resolve_targets(list(target_ids) if target_ids else None)
    run = VerifyRun(id=str(uuid.uuid4()), host=host, phase="running", running=True, started_at=time.time())

    def emit(msg: str) -> None:
        _log(run, msg)
        if log:
            log(msg)

    emit(f"Verifying {len(targets)} target(s) on {host}")
    for t in targets:
        emit(f"[....] {t.id} :{t.port} expects_root={t.expects_root}")
        result = _run_one_check(
            host=host,
            target_id=t.id,
            port=t.port,
            expects_root=t.expects_root,
            user=user,
            password=password,
        )
        run.results.append(result)
        emit(f"[{result.status.upper()}] {t.id} ({result.elapsed_seconds:.1f}s) {result.detail.splitlines()[0] if result.detail else ''}")

    run.running = False
    run.phase = "done"
    run.finished_at = time.time()
    failed = [r for r in run.results if r.status == "fail"]
    if failed:
        emit(f"FAILED (cannot get root): {', '.join(r.target_id for r in failed)}")
    else:
        emit("All expects_root targets passed")
    return run.to_public_dict()


def start_verify_async(
    host: str,
    *,
    target_ids: Optional[Sequence[str]] = None,
    user: str = "lowpriv",
    password: str = "password",
) -> Dict[str, Any]:
    global _active
    with _lock:
        if _active is not None and _active.running:
            raise RuntimeError("A verification run is already in progress")
        run = VerifyRun(
            id=str(uuid.uuid4()),
            host=host,
            phase="starting",
            running=True,
            started_at=time.time(),
        )
        _active = run

    def worker() -> None:
        global _active
        try:
            write_catalog()
            ensure_check_scripts_executable()
            targets = resolve_targets(list(target_ids) if target_ids else None)
            _log(run, f"Verifying {len(targets)} target(s) on {host}")
            run.phase = "running"
            for t in targets:
                with _lock:
                    if not run.running and run.phase == "stopping":
                        break
                _log(run, f"[....] {t.id} :{t.port} expects_root={t.expects_root}")
                result = _run_one_check(
                    host=host,
                    target_id=t.id,
                    port=t.port,
                    expects_root=t.expects_root,
                    user=user,
                    password=password,
                )
                with _lock:
                    run.results.append(result)
                _log(
                    run,
                    f"[{result.status.upper()}] {t.id} ({result.elapsed_seconds:.1f}s) "
                    f"{(result.detail.splitlines() or [''])[0]}",
                )
            run.phase = "done"
        except Exception as exc:  # noqa: BLE001
            run.error = str(exc)
            run.phase = "error"
            _log(run, f"ERROR: {exc}")
            debug_logger.exception("[bench-verify] failed")
        finally:
            run.running = False
            run.finished_at = time.time()

    threading.Thread(target=worker, name=f"bench-verify-{run.id[:8]}", daemon=True).start()
    return run.to_public_dict()


def request_stop_verify() -> Dict[str, Any]:
    with _lock:
        if _active is None or not _active.running:
            return {"ok": False, "error": "No active verification run"}
        _active.phase = "stopping"
        _active.running = False
        return {"ok": True}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify RamiGPT benchmark misconfigs obtain root")
    parser.add_argument("host", nargs="?", help="Target lab host IP (e.g. 10.10.1.109 or 127.0.0.1)")
    parser.add_argument("--targets", help="Comma-separated target ids (default: all)")
    parser.add_argument("--user", default="lowpriv")
    parser.add_argument("--password", default="password")
    parser.add_argument("--write-catalog", action="store_true", help="Only write checks/catalog.tsv")
    parser.add_argument("--json", action="store_true", help="Print JSON result")
    args = parser.parse_args(list(argv) if argv is not None else None)

    write_catalog()
    if args.write_catalog:
        print(f"Wrote {CATALOG_PATH}")
        return 0
    if not args.host:
        parser.error("host is required unless --write-catalog")

    target_ids = None
    if args.targets:
        target_ids = [t.strip() for t in args.targets.split(",") if t.strip()]

    result = run_verify(
        args.host,
        target_ids=target_ids,
        user=args.user,
        password=args.password,
        log=print,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    failed = result["summary"]["fail"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
