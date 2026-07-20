"""Upload and run BeRoot on a remote host."""

from __future__ import annotations

import tarfile
import tempfile
from pathlib import Path

from ramigpt.paths import BEROOT_DIR, ensure_runtime_dirs
from ramigpt.web.shell.ssh_remote import _sh_single_quote, _ssh_run_or_shell

def _pack_beroot_archive(dest: Path) -> None:
    """
    Pack tools/beroot/Linux into dest as Linux/... for remote extraction.

    Skips local scan downloads and macOS junk so the upload stays small/portable.
    """
    src = BEROOT_DIR
    with tarfile.open(dest, "w:gz") as tar:
        for path in sorted(src.rglob("*")):
            if path.name.startswith("._") or path.name in {".DS_Store", "__MACOSX"}:
                continue
            try:
                rel = path.relative_to(src)
            except ValueError:
                continue
            if rel.parts and rel.parts[0] == "downloaded":
                continue
            if not (path.is_file() or path.is_dir()):
                continue
            tar.add(path, arcname=str(Path("Linux") / rel), recursive=False)


def _upload_beroot_tree(ssh_conn, *, slog=None) -> None:
    """
    Upload BeRoot to /tmp/Linux without relying on remote GNU tar.

    pwntools upload_dir runs ``tar -xzf`` on the target; GNU tar 1.35 hits ENOSYS
    under some Docker/seccomp profiles (snap Docker + older kernels). Python's
    tarfile works on those same hosts, so pack locally and extract with python3.
    """
    remote_archive = "/tmp/ramigpt-beroot-linux.tgz"
    with tempfile.TemporaryDirectory(prefix="ramigpt-beroot-") as tmp:
        archive = Path(tmp) / "beroot-linux.tgz"
        _pack_beroot_archive(archive)
        if slog is not None:
            slog.info(
                f"beroot: uploading archive ({archive.stat().st_size} bytes) → {remote_archive}"
            )
        ssh_conn.upload(str(archive), remote_archive)

    extract_cmd = (
        "rm -rf /tmp/Linux && "
        "python3 -c "
        "\"import tarfile; tarfile.open('/tmp/ramigpt-beroot-linux.tgz','r:gz')"
        ".extractall('/tmp')\" && "
        "rm -f /tmp/ramigpt-beroot-linux.tgz && "
        "test -f /tmp/Linux/beroot.py"
    )
    if slog is not None:
        slog.info("beroot: extracting with remote python3 (avoids broken GNU tar)")
    buf = _ssh_run_or_shell(ssh_conn, extract_cmd, timeout=60, slog=slog)
    # Soft-check: command already ends with test -f; re-raise with buffer if needed.
    check = _ssh_run_or_shell(
        ssh_conn,
        "test -f /tmp/Linux/beroot.py && echo BEROOT_READY",
        timeout=10,
        slog=slog,
    )
    if b"BEROOT_READY" not in (check or b""):
        raise RuntimeError(
            "BeRoot upload/extract failed on remote host "
            f"(python3 extract). Tail: {(buf or b'')[-400]!r} / {(check or b'')[-400]!r}"
        )


def upload_and_run_beroot(ssh_conn, *, password: str, slog=None, timeout: int = 180) -> str:
    """
    Upload tools/beroot/Linux to /tmp/Linux on the remote host, run BeRoot,
    and return the scanner stdout (also written remotely to /tmp/beroot.txt).
    """
    ensure_runtime_dirs()
    if not BEROOT_DIR.is_dir() or not (BEROOT_DIR / "beroot.py").is_file():
        raise FileNotFoundError(f"BeRoot package missing at {BEROOT_DIR}")

    if slog is not None:
        slog.info(f"beroot: uploading {BEROOT_DIR} → /tmp/Linux")
    _upload_beroot_tree(ssh_conn, slog=slog)

    pw = _sh_single_quote(password)
    # cd into the package so `from beroot.run import run` resolves.
    remote_cmd = (
        "cd /tmp/Linux && "
        "{ python3 beroot.py --password "
        + pw
        + " || python beroot.py --password "
        + pw
        + "; } > /tmp/beroot.txt 2>&1; "
        "echo __BEROOT_EXIT__:$?; "
        "wc -c /tmp/beroot.txt"
    )
    if slog is not None:
        slog.info("beroot: starting remote scan (this can take a minute)")

    buf = _ssh_run_or_shell(
        ssh_conn, remote_cmd, timeout=max(30, int(timeout)), slog=slog
    )

    # Prefer the file BeRoot wrote; fall back to captured stdout.
    text = ""
    try:
        raw = ssh_conn.download_data("/tmp/beroot.txt")
        if isinstance(raw, bytes):
            text = raw.decode("utf-8", errors="replace")
        else:
            text = str(raw or "")
    except Exception as exc:  # noqa: BLE001
        if slog is not None:
            slog.warning(f"beroot: download /tmp/beroot.txt failed: {exc}")
        text = (buf or b"").decode("utf-8", errors="replace")

    text = (text or "").strip()
    if not text:
        raise RuntimeError(
            "BeRoot produced empty output. "
            f"Remote buffer tail: {(buf or b'')[-500:]!r}"
        )

    # BeRoot's sudo -ll parser often misses modern NOPASSWD listings; append a
    # plain `sudo -l` capture so privilege-escalation rules stay visible to the AI.
    try:
        probe_cmd = (
            f"echo {_sh_single_quote(password)} | sudo -S -l 2>/dev/null; "
            "sudo -ln 2>/dev/null; echo __SUDO_L_DONE__"
        )
        pbuf = _ssh_run_or_shell(ssh_conn, probe_cmd, timeout=20, slog=slog)
        sudo_l = (pbuf or b"").decode("utf-8", errors="replace")
        sudo_l = sudo_l.split("__SUDO_L_DONE__")[0]
        lines = [
            ln for ln in sudo_l.splitlines()
            if ln.strip() and not ln.strip().startswith("$")
            and "sudo -S -l" not in ln and "sudo -ln" not in ln
        ]
        sudo_clean = "\n".join(lines).strip()
        if sudo_clean and (
            "may run" in sudo_clean.lower()
            or "NOPASSWD" in sudo_clean
            or "sudoers" in sudo_clean.lower()
            or "(root)" in sudo_clean
        ):
            text = (
                text
                + "\n\n################ sudo -l (runner capture) ################\n\n"
                + sudo_clean
                + "\n"
            )
    except Exception as exc:  # noqa: BLE001
        if slog is not None:
            slog.warning(f"beroot: sudo -l enrichment skipped: {exc}")

    if slog is not None:
        slog.info(f"beroot: scan finished ({len(text)} chars)")
        slog.block("BEROOT_OUTPUT", text[:20000])
    return text


def _run_linenum_on_remote(ssh_conn, *, password: str, slog=None, timeout: int = 300) -> str:
    """Run LinEnum on the remote host via the shared tools.linenum runner."""
    return upload_and_run_linenum(
        ssh_conn,
        password=password,
        sh_quote=_sh_single_quote,
        ssh_run=_ssh_run_or_shell,
        slog=slog,
        timeout=timeout,
    )


def _run_linpeas_on_remote(ssh_conn, *, password: str, slog=None, timeout: int = 600) -> str:
    """Run LinPEAS on the remote host via the shared tools.linpeas runner."""
    return upload_and_run_linpeas(
        ssh_conn,
        password=password,
        sh_quote=_sh_single_quote,
        ssh_run=_ssh_run_or_shell,
        slog=slog,
        timeout=timeout,
    )
