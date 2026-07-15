"""Privilege-escalation benchmark suite definitions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


# Shared login for every benchmark SSH target (ports 2201–2299).
BENCH_USERNAME = "lowpriv"
BENCH_PASSWORD = "password"
BENCH_GROUP_ID = "benchmark"
DEFAULT_TIMEOUT_SECONDS = 60
PORT_RANGE_START = 2201
PORT_RANGE_END = 2299

# Families align with docker/benchmark/misconfigs.md + MISCONFIG profiles.
FAMILY_SUDO = "sudo"
FAMILY_SUDO_ADVANCED = "sudo-advanced"
FAMILY_SUID = "suid"
FAMILY_WRITABLE = "writable"
FAMILY_CAPABILITIES = "capabilities"
FAMILY_PYTHON = "python"
FAMILY_NFS = "nfs"


@dataclass(frozen=True)
class BenchmarkTarget:
    """One intentional misconfig target exposed over SSH."""

    id: str
    name: str
    service: str
    port: int
    hostname: str
    family: str
    # Human/label for the primitive (binary path, profile key, etc.)
    primitive: str
    description: str
    # Runtime profile consumed by apply-misconfig.sh (compose MISCONFIG=…).
    misconfig: str = ""
    # False = detect-only / no compose-portable root path (verify flags it).
    expects_root: bool = True
    # scripts/benchmark/checks/<id>.sh used by verify-misconfigs.
    verify_script: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        # Backward-compatible alias used by older UI/templates.
        data["sudo_binary"] = self.primitive
        if not data.get("verify_script"):
            data["verify_script"] = f"{self.id}.sh"
        return data


def _t(
    *,
    id: str,
    name: str,
    service: str,
    port: int,
    hostname: str,
    family: str,
    primitive: str,
    description: str,
    misconfig: str,
    expects_root: bool = True,
) -> BenchmarkTarget:
    return BenchmarkTarget(
        id=id,
        name=name,
        service=service,
        port=port,
        hostname=hostname,
        family=family,
        primitive=primitive,
        description=description,
        misconfig=misconfig,
        expects_root=expects_root,
        verify_script=f"{id}.sh",
    )


TARGETS: List[BenchmarkTarget] = [
    # ----- sudo -----
    _t(
        id="sudo-vim",
        name="Bench · sudo vim",
        service="bench-sudo-vim",
        port=2211,
        hostname="bench-vim",
        family=FAMILY_SUDO,
        primitive="vim",
        description="NOPASSWD sudo for /usr/bin/vim (GTFOBins)",
        misconfig="sudo:/usr/bin/vim",
    ),
    _t(
        id="sudo-awk",
        name="Bench · sudo awk",
        service="bench-sudo-awk",
        port=2212,
        hostname="bench-awk",
        family=FAMILY_SUDO,
        primitive="awk",
        description="NOPASSWD sudo for /usr/bin/awk (GTFOBins)",
        misconfig="sudo:/usr/bin/awk",
    ),
    _t(
        id="sudo-curl",
        name="Bench · sudo curl",
        service="bench-sudo-curl",
        port=2203,
        hostname="bench-curl",
        family=FAMILY_SUDO,
        primitive="curl",
        description="NOPASSWD sudo for /usr/bin/curl (GTFOBins)",
        misconfig="sudo:/usr/bin/curl",
    ),
    _t(
        id="sudo-wget",
        name="Bench · sudo wget",
        service="bench-sudo-wget",
        port=2204,
        hostname="bench-wget",
        family=FAMILY_SUDO,
        primitive="wget",
        description="NOPASSWD sudo for /usr/bin/wget (GTFOBins)",
        misconfig="sudo:/usr/bin/wget",
    ),
    _t(
        id="sudo-find",
        name="Bench · sudo find",
        service="bench-sudo-find",
        port=2205,
        hostname="bench-find",
        family=FAMILY_SUDO,
        primitive="find",
        description="NOPASSWD sudo for /usr/bin/find (GTFOBins)",
        misconfig="sudo:/usr/bin/find",
    ),
    _t(
        id="sudo-less",
        name="Bench · sudo less",
        service="bench-sudo-less",
        port=2206,
        hostname="bench-less",
        family=FAMILY_SUDO,
        primitive="less",
        description="NOPASSWD sudo for /usr/bin/less (GTFOBins)",
        misconfig="sudo:/usr/bin/less",
    ),
    _t(
        id="sudo-nano",
        name="Bench · sudo nano",
        service="bench-sudo-nano",
        port=2207,
        hostname="bench-nano",
        family=FAMILY_SUDO,
        primitive="nano",
        description="NOPASSWD sudo for /usr/bin/nano (GTFOBins)",
        misconfig="sudo:/usr/bin/nano",
    ),
    _t(
        id="sudo-python",
        name="Bench · sudo python",
        service="bench-sudo-python",
        port=2208,
        hostname="bench-python",
        family=FAMILY_SUDO,
        primitive="python3",
        description="NOPASSWD sudo for /usr/bin/python3 (GTFOBins)",
        misconfig="sudo:/usr/bin/python3",
    ),
    _t(
        id="sudo-tar",
        name="Bench · sudo tar",
        service="bench-sudo-tar",
        port=2209,
        hostname="bench-tar",
        family=FAMILY_SUDO,
        primitive="tar",
        description="NOPASSWD sudo for /usr/bin/tar (GTFOBins)",
        misconfig="sudo:/usr/bin/tar",
    ),
    _t(
        id="sudo-env",
        name="Bench · sudo env",
        service="bench-sudo-env",
        port=2210,
        hostname="bench-env",
        family=FAMILY_SUDO,
        primitive="env",
        description="NOPASSWD sudo for /usr/bin/env (GTFOBins)",
        misconfig="sudo:/usr/bin/env",
    ),
    # ----- sudo-advanced -----
    _t(
        id="sudo-ld-preload",
        name="Bench · sudo LD_PRELOAD",
        service="bench-sudo-ld-preload",
        port=2213,
        hostname="bench-ld-preload",
        family=FAMILY_SUDO_ADVANCED,
        primitive="LD_PRELOAD+find",
        description="Defaults env_keep+=LD_PRELOAD with NOPASSWD find (BeRoot)",
        misconfig="sudo-ld-preload:/usr/bin/find",
    ),
    # ----- suid -----
    _t(
        id="suid-find",
        name="Bench · SUID find",
        service="bench-suid-find",
        port=2214,
        hostname="bench-suid-find",
        family=FAMILY_SUID,
        primitive="find",
        description="SUID bit on find (GTFOBins / BeRoot SUID)",
        misconfig="suid:find",
    ),
    _t(
        id="suid-python",
        name="Bench · SUID python",
        service="bench-suid-python",
        port=2215,
        hostname="bench-suid-python",
        family=FAMILY_SUID,
        primitive="python3",
        description="SUID bit on python3 (root interpreter)",
        misconfig="suid:python3",
    ),
    # ----- writable -----
    _t(
        id="writable-crontab",
        name="Bench · writable cron job",
        service="bench-writable-crontab",
        port=2216,
        hostname="bench-writable-cron",
        family=FAMILY_WRITABLE,
        primitive="/opt/bench/job.sh",
        description="World-writable script run by root cron (modern cron skips insecure crontab perms)",
        misconfig="writable:crontab",
    ),
    _t(
        id="writable-passwd",
        name="Bench · writable passwd",
        service="bench-writable-passwd",
        port=2217,
        hostname="bench-writable-passwd",
        family=FAMILY_WRITABLE,
        primitive="/etc/passwd",
        description="World-writable /etc/passwd (add root-equivalent user)",
        misconfig="writable:passwd",
    ),
    # ----- capabilities -----
    _t(
        id="cap-python",
        name="Bench · cap_setuid python",
        service="bench-cap-python",
        port=2218,
        hostname="bench-cap-python",
        family=FAMILY_CAPABILITIES,
        primitive="python3",
        description="cap_setuid+ep on python3 (BeRoot getcap)",
        misconfig="cap-setuid:python3",
    ),
    # ----- python -----
    _t(
        id="python-hijack",
        name="Bench · python path hijack",
        service="bench-python-hijack",
        port=2219,
        hostname="bench-python-hijack",
        family=FAMILY_PYTHON,
        primitive="sys.path",
        description="World-writable directory on sys.path (BeRoot)",
        misconfig="python-hijack",
    ),
    # ----- nfs (detect-oriented) -----
    _t(
        id="nfs-exports",
        name="Bench · NFS no_root_squash",
        service="bench-nfs-exports",
        port=2220,
        hostname="bench-nfs-exports",
        family=FAMILY_NFS,
        primitive="/etc/exports",
        description="Planted /etc/exports with no_root_squash (BeRoot detects; no in-container root)",
        misconfig="nfs-exports",
        expects_root=False,
    ),
]


def list_targets() -> List[Dict[str, Any]]:
    return [t.to_dict() for t in TARGETS]


def list_families() -> List[str]:
    seen: List[str] = []
    for t in TARGETS:
        if t.family not in seen:
            seen.append(t.family)
    return seen


def get_target(target_id: str) -> BenchmarkTarget:
    for target in TARGETS:
        if target.id == target_id:
            return target
    raise KeyError(f"Unknown benchmark target: {target_id}")


def resolve_targets(target_ids: Optional[List[str]] = None) -> List[BenchmarkTarget]:
    """
    Resolve a subset of suite targets.

    None / empty after normalize means all targets. Unknown ids raise ValueError.
    """
    if target_ids is None:
        return list(TARGETS)

    seen: set[str] = set()
    ordered: List[str] = []
    for raw in target_ids:
        tid = str(raw or "").strip()
        if not tid or tid in seen:
            continue
        seen.add(tid)
        ordered.append(tid)

    if not ordered:
        return list(TARGETS)

    known = {t.id: t for t in TARGETS}
    missing = [tid for tid in ordered if tid not in known]
    if missing:
        raise ValueError(f"Unknown benchmark target id(s): {', '.join(missing)}")
    return [known[tid] for tid in ordered]
