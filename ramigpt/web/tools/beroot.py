"""Upload and run BeRoot on a remote host."""

from __future__ import annotations

import tarfile
import tempfile
from pathlib import Path

from ramigpt.paths import BEROOT_DIR, ensure_runtime_dirs
from ramigpt.web.shell.ssh_remote import _sh_single_quote, _ssh_run_or_shell

_REMOTE_ARCHIVE = "/tmp/ramigpt-beroot-linux.tgz"
_BEROOT_PKG_MARKER = "__BEROOT_PKG__:"


def _coerce_ssh_bytes(data: object) -> bytes:
    if data is None:
        return b""
    if isinstance(data, bytes):
        return data
    return str(data).encode("utf-8", errors="replace")


def _bytes_tail(data: object, limit: int = 400) -> bytes:
    """Return the last ``limit`` bytes without indexing errors on empty buffers."""
    return _coerce_ssh_bytes(data)[-limit:]


def _parse_beroot_pkg_path(output: object) -> str | None:
    text = _coerce_ssh_bytes(output).decode("utf-8", errors="replace")
    for line in text.splitlines():
        if line.startswith(_BEROOT_PKG_MARKER):
            path = line[len(_BEROOT_PKG_MARKER) :].strip()
            if path:
                return path
    return None


def _upload_extract_failed_error(*, stage: str, buf: object, check: object) -> RuntimeError:
    return RuntimeError(
        f"BeRoot upload/extract failed on remote host ({stage}). "
        f"Tail: {_bytes_tail(buf)!r} / {_bytes_tail(check)!r}"
    )

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


def _upload_beroot_tree(ssh_conn, *, slog=None) -> str:
    """
    Upload BeRoot and extract it into a fresh per-run directory under
    ``/tmp/ramigpt-beroot-<uid>/``.

    Returns the remote directory that contains ``beroot.py`` (…/Linux).
    """
    remote_archive = _REMOTE_ARCHIVE
    with tempfile.TemporaryDirectory(prefix="ramigpt-beroot-") as tmp:
        archive = Path(tmp) / "beroot-linux.tgz"
        _pack_beroot_archive(archive)
        if slog is not None:
            slog.info(
                f"beroot: uploading archive ({archive.stat().st_size} bytes) → {remote_archive}"
            )
        ssh_conn.upload(str(archive), remote_archive)

    extract_cmd = (
        "python3 - <<'PY'\n"
        "import os\n"
        "import stat\n"
        "import tarfile\n"
        "import tempfile\n"
        f"archive = {remote_archive!r}\n"
        "real_uid = os.getuid()\n"
        "real_gid = os.getgid()\n"
        "base = '/tmp/ramigpt-beroot-' + str(real_uid)\n"
        "os.makedirs(base, exist_ok=True)\n"
        "pkg = tempfile.mkdtemp(prefix='pkg.', dir=base)\n"
        "tarfile.open(archive, 'r:gz').extractall(pkg)\n"
        "os.remove(archive)\n"
        "if os.geteuid() == 0 and real_uid != 0:\n"
        "    def _fix_tree(path):\n"
        "        for dirpath, dirnames, filenames in os.walk(path, topdown=False):\n"
        "            for name in filenames:\n"
        "                fp = os.path.join(dirpath, name)\n"
        "                os.chown(fp, real_uid, real_gid)\n"
        "                os.chmod(fp, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)\n"
        "            for name in dirnames:\n"
        "                dp = os.path.join(dirpath, name)\n"
        "                os.chown(dp, real_uid, real_gid)\n"
        "                os.chmod(dp, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)\n"
        "        os.chown(path, real_uid, real_gid)\n"
        "        os.chmod(path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)\n"
        "    _fix_tree(pkg)\n"
        "    try:\n"
        "        os.chown(base, real_uid, real_gid)\n"
        "        os.chmod(base, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)\n"
        "    except OSError:\n"
        "        pass\n"
        "linux = os.path.join(pkg, 'Linux')\n"
        "script = os.path.join(linux, 'beroot.py')\n"
        "if not os.path.isfile(script):\n"
        "    raise SystemExit('beroot.py missing after extract')\n"
        f"print({_BEROOT_PKG_MARKER!r} + linux)\n"
        "PY"
    )
    if slog is not None:
        slog.info("beroot: extracting with remote python3 (avoids broken GNU tar)")
    buf = _ssh_run_or_shell(ssh_conn, extract_cmd, timeout=60, slog=slog)
    remote_linux_dir = _parse_beroot_pkg_path(buf)
    if remote_linux_dir:
        return remote_linux_dir

    raise _upload_extract_failed_error(stage="python3 extract", buf=buf, check=b"")


def upload_and_run_beroot(ssh_conn, *, password: str, slog=None, timeout: int = 180) -> str:
    """
    Upload tools/beroot/Linux to a fresh directory on the remote host, run BeRoot,
    and return the scanner stdout (also written remotely beside the package).
    """
    ensure_runtime_dirs()
    if not BEROOT_DIR.is_dir() or not (BEROOT_DIR / "beroot.py").is_file():
        raise FileNotFoundError(f"BeRoot package missing at {BEROOT_DIR}")

    if slog is not None:
        slog.info(f"beroot: uploading {BEROOT_DIR} → remote workspace")
    remote_linux_dir = _upload_beroot_tree(ssh_conn, slog=slog)
    remote_pkg_dir = remote_linux_dir.rsplit("/", 1)[0]
    remote_output = f"{remote_pkg_dir}/beroot.txt"
    linux_q = _sh_single_quote(remote_linux_dir)
    output_q = _sh_single_quote(remote_output)

    pw = _sh_single_quote(password)
    # cd into the package so `from beroot.run import run` resolves.
    remote_cmd = (
        f"cd {linux_q} && "
        "{ python3 beroot.py --password "
        + pw
        + " || python beroot.py --password "
        + pw
        + f"; }} > {output_q} 2>&1; "
        "echo __BEROOT_EXIT__:$?; "
        f"wc -c {output_q}"
    )
    if slog is not None:
        slog.info("beroot: starting remote scan (this can take a minute)")

    buf = _ssh_run_or_shell(
        ssh_conn, remote_cmd, timeout=max(30, int(timeout)), slog=slog
    )

    # Prefer the file BeRoot wrote; fall back to captured stdout.
    text = ""
    try:
        raw = ssh_conn.download_data(remote_output)
        if isinstance(raw, bytes):
            text = raw.decode("utf-8", errors="replace")
        else:
            text = str(raw or "")
    except Exception as exc:  # noqa: BLE001
        if slog is not None:
            slog.warning(f"beroot: download {remote_output} failed: {exc}")
        text = (buf or b"").decode("utf-8", errors="replace")

    text = (text or "").strip()
    if not text:
        raise RuntimeError(
            "BeRoot produced empty output. "
            f"Remote buffer tail: {_bytes_tail(buf, 500)!r}"
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
