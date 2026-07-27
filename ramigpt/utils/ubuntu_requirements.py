"""Ensure Ubuntu/Debian host packages needed by RamiGPT are present.

Covers the system deps that previously caused opaque benchmark/deploy failures
(e.g. missing ``sshpass``, missing OpenSSH client). Safe to call repeatedly;
installs only what is missing.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

LogFn = Callable[[str], None]

_LOCK = threading.Lock()
_ENSURED = False

# ansible-core range that still supports Python 3.8 on remote lab hosts
# (Ubuntu 20.04). Keep in sync with requirements.txt.
ANSIBLE_CORE_MIN = (2, 18, 0)
ANSIBLE_CORE_MAX_EXCLUSIVE = (2, 20, 0)


@dataclass(frozen=True)
class AptRequirement:
    """One apt package and how to detect it on PATH / dpkg."""

    package: str
    reason: str
    binaries: Tuple[str, ...] = ()
    """Any of these commands on PATH means the package is present."""
    dpkg_name: Optional[str] = None
    """Optional explicit dpkg package name (defaults to ``package``)."""

    @property
    def query_name(self) -> str:
        return self.dpkg_name or self.package


# Host packages required for local HTTPS, SSH probes, Ansible password auth,
# and benchmark verify scripts.
UBUNTU_APT_REQUIREMENTS: Tuple[AptRequirement, ...] = (
    AptRequirement(
        package="openssh-client",
        binaries=("ssh", "scp"),
        reason="SSH client for Ansible deploy and lab probes",
    ),
    AptRequirement(
        package="sshpass",
        binaries=("sshpass",),
        reason="Non-interactive SSH passwords (Ansible + benchmark verify)",
    ),
    AptRequirement(
        package="openssl",
        binaries=("openssl",),
        reason="TLS certificate generation for the local HTTPS UI",
    ),
    AptRequirement(
        package="ca-certificates",
        binaries=(),
        reason="CA trust store for HTTPS / outbound TLS",
    ),
)


@dataclass
class RequirementStatus:
    requirement: AptRequirement
    present: bool
    detail: str = ""


@dataclass
class EnsureResult:
    platform: str
    debian_like: bool
    checked: List[RequirementStatus] = field(default_factory=list)
    installed: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    ansible_ok: bool = True
    ansible_detail: str = ""
    skipped: bool = False
    message: str = ""

    @property
    def ok(self) -> bool:
        if self.skipped:
            return True
        return not self.missing and self.ansible_ok


def _default_log(message: str) -> None:
    try:
        from ramigpt.utils.logging import debug_logger

        debug_logger.info(f"[ubuntu-requirements] {message}")
    except Exception:  # noqa: BLE001
        pass


def requirements_skipped() -> bool:
    return os.getenv("RAMIGPT_SKIP_UBUNTU_REQUIREMENTS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def read_os_release(path: Path = Path("/etc/os-release")) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return data
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, raw = line.partition("=")
        data[key] = raw.strip().strip('"').strip("'")
    return data


def is_debian_like(os_release: Optional[dict[str, str]] = None) -> bool:
    info = os_release if os_release is not None else read_os_release()
    id_ = (info.get("ID") or "").lower()
    like = (info.get("ID_LIKE") or "").lower()
    if id_ in {"ubuntu", "debian", "linuxmint", "pop", "elementary", "raspbian"}:
        return True
    return any(token in like.split() for token in ("ubuntu", "debian"))


def _dpkg_installed(package: str) -> Optional[bool]:
    """Return True/False when dpkg-query works; None if dpkg is unavailable."""
    dpkg_query = shutil.which("dpkg-query")
    if not dpkg_query:
        return None
    try:
        proc = subprocess.run(
            [dpkg_query, "-W", "-f=${Status}", package],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    status = (proc.stdout or "").strip().lower()
    return proc.returncode == 0 and "install ok installed" in status


def is_requirement_present(req: AptRequirement) -> Tuple[bool, str]:
    for binary in req.binaries:
        path = shutil.which(binary)
        if path:
            return True, f"{binary} → {path}"
    dpkg_state = _dpkg_installed(req.query_name)
    if dpkg_state is True:
        return True, f"dpkg:{req.query_name} installed"
    if dpkg_state is False:
        return False, f"dpkg:{req.query_name} not installed"
    if req.binaries:
        return False, f"missing binaries: {', '.join(req.binaries)}"
    return False, f"cannot verify {req.package} (no dpkg-query)"


def check_apt_requirements(
    requirements: Sequence[AptRequirement] = UBUNTU_APT_REQUIREMENTS,
) -> List[RequirementStatus]:
    statuses: List[RequirementStatus] = []
    for req in requirements:
        present, detail = is_requirement_present(req)
        statuses.append(RequirementStatus(requirement=req, present=present, detail=detail))
    return statuses


def _parse_version_tuple(version: str) -> Tuple[int, ...]:
    parts: List[int] = []
    for chunk in version.split("."):
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts) if parts else (0,)


def check_ansible_core_version() -> Tuple[bool, str]:
    """Return whether installed ansible-core matches the supported range."""
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:  # pragma: no cover
        from importlib_metadata import PackageNotFoundError, version  # type: ignore

    try:
        ver = version("ansible-core")
    except PackageNotFoundError:
        # ansible-playbook might still be on PATH from a system package.
        if shutil.which("ansible-playbook"):
            return False, (
                "ansible-playbook is on PATH but ansible-core is not installed in this "
                f"Python env — pip install 'ansible-core>={ANSIBLE_CORE_MIN[0]}."
                f"{ANSIBLE_CORE_MIN[1]},<{ANSIBLE_CORE_MAX_EXCLUSIVE[0]}."
                f"{ANSIBLE_CORE_MAX_EXCLUSIVE[1]}'"
            )
        return False, (
            "ansible-core is not installed — "
            f"pip install 'ansible-core>={ANSIBLE_CORE_MIN[0]}.{ANSIBLE_CORE_MIN[1]},"
            f"<{ANSIBLE_CORE_MAX_EXCLUSIVE[0]}.{ANSIBLE_CORE_MAX_EXCLUSIVE[1]}'"
        )

    parsed = _parse_version_tuple(ver)
    if parsed < ANSIBLE_CORE_MIN or parsed >= ANSIBLE_CORE_MAX_EXCLUSIVE:
        return False, (
            f"ansible-core {ver} is outside the supported range "
            f">={ANSIBLE_CORE_MIN[0]}.{ANSIBLE_CORE_MIN[1]},"
            f"<{ANSIBLE_CORE_MAX_EXCLUSIVE[0]}.{ANSIBLE_CORE_MAX_EXCLUSIVE[1]} "
            "(needed for Ubuntu 20.04 / Python 3.8 lab hosts). "
            f"pip install -U 'ansible-core>={ANSIBLE_CORE_MIN[0]}.{ANSIBLE_CORE_MIN[1]},"
            f"<{ANSIBLE_CORE_MAX_EXCLUSIVE[0]}.{ANSIBLE_CORE_MAX_EXCLUSIVE[1]}'"
        )
    if not shutil.which("ansible-playbook"):
        return False, (
            f"ansible-core {ver} is installed but ansible-playbook is not on PATH "
            "(activate the same venv used to install requirements.txt)"
        )
    return True, f"ansible-core {ver}"


def _apt_get_bin() -> Optional[str]:
    return shutil.which("apt-get")


def _can_run_as_root() -> bool:
    try:
        return os.geteuid() == 0
    except AttributeError:  # pragma: no cover - non-Unix
        return False


def _sudo_bin() -> Optional[str]:
    return shutil.which("sudo")


def _build_install_command(packages: Sequence[str]) -> List[str]:
    apt_get = _apt_get_bin()
    if not apt_get:
        raise RuntimeError("apt-get not found — cannot install Ubuntu packages automatically")
    inner = [
        apt_get,
        "install",
        "-y",
        "--no-install-recommends",
        *packages,
    ]
    if _can_run_as_root():
        return inner
    sudo = _sudo_bin()
    if not sudo:
        raise RuntimeError(
            "Missing packages require root to install via apt, but sudo was not found. "
            f"Install manually: sudo apt-get install -y {' '.join(packages)}"
        )
    return [sudo, "-n", *inner]


def _run_apt(cmd: Sequence[str], *, log: LogFn, timeout: int = 300) -> None:
    log(f"$ {' '.join(cmd)}")
    env = {
        **os.environ,
        "DEBIAN_FRONTEND": "noninteractive",
        "NEEDRESTART_MODE": "a",
    }
    try:
        proc = subprocess.run(
            list(cmd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Timed out running: {' '.join(cmd)}") from exc
    except FileNotFoundError as exc:
        raise RuntimeError(f"Command not found: {cmd[0]}") from exc

    out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    if out:
        # Keep logs readable — last ~40 lines.
        lines = out.splitlines()
        clipped = lines if len(lines) <= 40 else lines[-40:]
        for line in clipped:
            log(line)
    if proc.returncode != 0:
        if "password is required" in out.lower() or "a password is required" in out.lower():
            pkgs = " ".join(arg for arg in cmd if not arg.startswith("-") and arg not in {"sudo", "apt-get", "install"})
            raise RuntimeError(
                "sudo needs a password to install packages. "
                f"Run once manually: sudo apt-get install -y {pkgs}"
            )
        raise RuntimeError(
            f"apt-get failed ({proc.returncode}): {' '.join(cmd)}\n{out[-2000:]}"
        )


def install_apt_packages(packages: Sequence[str], *, log: LogFn = _default_log) -> None:
    """Install missing apt packages (root or passwordless sudo)."""
    pkgs = [p for p in packages if p]
    if not pkgs:
        return
    apt_get = _apt_get_bin()
    if not apt_get:
        raise RuntimeError("apt-get not found")

    update_cmd: List[str]
    if _can_run_as_root():
        update_cmd = [apt_get, "update", "-qq"]
    else:
        sudo = _sudo_bin()
        if not sudo:
            raise RuntimeError(
                f"Install manually: sudo apt-get install -y {' '.join(pkgs)}"
            )
        update_cmd = [sudo, "-n", apt_get, "update", "-qq"]

    try:
        _run_apt(update_cmd, log=log, timeout=180)
    except RuntimeError as exc:
        # Update failures are common offline; still try install from cache.
        log(f"apt-get update warning (continuing): {exc}")

    _run_apt(_build_install_command(pkgs), log=log, timeout=300)


def ensure_ubuntu_requirements(
    *,
    install: bool = True,
    force: bool = False,
    log: Optional[LogFn] = None,
    requirements: Sequence[AptRequirement] = UBUNTU_APT_REQUIREMENTS,
    check_ansible: bool = True,
) -> EnsureResult:
    """
    Check (and optionally install) Ubuntu host requirements.

    On non-Debian systems, only reports missing binaries (no apt install).
    Set ``RAMIGPT_SKIP_UBUNTU_REQUIREMENTS=1`` to no-op.
    """
    global _ENSURED
    logger = log or _default_log

    if requirements_skipped():
        return EnsureResult(
            platform=platform.platform(),
            debian_like=False,
            skipped=True,
            message="Skipped via RAMIGPT_SKIP_UBUNTU_REQUIREMENTS",
        )

    with _LOCK:
        if _ENSURED and not force:
            ansible_ok, ansible_detail = (
                check_ansible_core_version() if check_ansible else (True, "skipped")
            )
            return EnsureResult(
                platform=platform.platform(),
                debian_like=is_debian_like(),
                ansible_ok=ansible_ok,
                ansible_detail=ansible_detail,
                message="Already ensured this process",
            )

        os_info = read_os_release()
        debian = is_debian_like(os_info)
        statuses = check_apt_requirements(requirements)
        missing_reqs = [s.requirement for s in statuses if not s.present]
        installed: List[str] = []

        if missing_reqs and install and debian:
            pkg_names = [r.package for r in missing_reqs]
            logger(
                "Installing missing Ubuntu packages: "
                + ", ".join(f"{r.package} ({r.reason})" for r in missing_reqs)
            )
            install_apt_packages(pkg_names, log=logger)
            installed = pkg_names
            statuses = check_apt_requirements(requirements)
            missing_reqs = [s.requirement for s in statuses if not s.present]
        elif missing_reqs and install and not debian:
            pkgs = " ".join(r.package for r in missing_reqs)
            raise RuntimeError(
                "Missing host tools for RamiGPT benchmark/deploy: "
                + ", ".join(f"{r.package} ({r.reason})" for r in missing_reqs)
                + f". This host is not Debian/Ubuntu — install equivalents manually "
                f"(Debian packages would be: {pkgs})."
            )
        elif missing_reqs and not install:
            pkgs = " ".join(r.package for r in missing_reqs)
            raise RuntimeError(
                "Missing Ubuntu packages: "
                + ", ".join(f"{r.package} ({r.reason})" for r in missing_reqs)
                + f". Install with: sudo apt-get install -y {pkgs}"
            )

        if missing_reqs:
            pkgs = " ".join(r.package for r in missing_reqs)
            raise RuntimeError(
                "Still missing after install attempt: "
                + ", ".join(r.package for r in missing_reqs)
                + f". Try: sudo apt-get install -y {pkgs}"
            )

        ansible_ok, ansible_detail = (
            check_ansible_core_version() if check_ansible else (True, "skipped")
        )
        if check_ansible and not ansible_ok:
            raise RuntimeError(ansible_detail)

        _ENSURED = True
        distro = os_info.get("PRETTY_NAME") or os_info.get("ID") or platform.system()
        message = (
            f"Ubuntu requirements OK on {distro}"
            + (f" (installed: {', '.join(installed)})" if installed else "")
        )
        logger(message)
        return EnsureResult(
            platform=platform.platform(),
            debian_like=debian,
            checked=statuses,
            installed=installed,
            missing=[],
            ansible_ok=ansible_ok,
            ansible_detail=ansible_detail,
            message=message,
        )


def reset_ubuntu_requirements_cache() -> None:
    """Test helper — clear the process-level ensured flag."""
    global _ENSURED
    with _LOCK:
        _ENSURED = False


def apt_install_hint(requirements: Iterable[AptRequirement] = UBUNTU_APT_REQUIREMENTS) -> str:
    pkgs = " ".join(r.package for r in requirements)
    return f"sudo apt-get install -y --no-install-recommends {pkgs}"
