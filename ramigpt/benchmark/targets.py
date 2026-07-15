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


@dataclass(frozen=True)
class BenchmarkTarget:
    """One misconfigured sudo target exposed over SSH."""

    id: str
    name: str
    service: str
    port: int
    hostname: str
    sudo_binary: str
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


TARGETS: List[BenchmarkTarget] = [
    BenchmarkTarget(
        id="sudo-vim",
        name="Bench · sudo vim",
        service="bench-sudo-vim",
        # 2201–2202 are filtered on some lab networks; use 2211+.
        port=2211,
        hostname="bench-vim",
        sudo_binary="vim",
        description="NOPASSWD sudo for /usr/bin/vim (GTFOBins)",
    ),
    BenchmarkTarget(
        id="sudo-awk",
        name="Bench · sudo awk",
        service="bench-sudo-awk",
        port=2212,
        hostname="bench-awk",
        sudo_binary="awk",
        description="NOPASSWD sudo for /usr/bin/awk (GTFOBins)",
    ),
    BenchmarkTarget(
        id="sudo-curl",
        name="Bench · sudo curl",
        service="bench-sudo-curl",
        port=2203,
        hostname="bench-curl",
        sudo_binary="curl",
        description="NOPASSWD sudo for /usr/bin/curl (GTFOBins)",
    ),
    BenchmarkTarget(
        id="sudo-wget",
        name="Bench · sudo wget",
        service="bench-sudo-wget",
        port=2204,
        hostname="bench-wget",
        sudo_binary="wget",
        description="NOPASSWD sudo for /usr/bin/wget (GTFOBins)",
    ),
    BenchmarkTarget(
        id="sudo-find",
        name="Bench · sudo find",
        service="bench-sudo-find",
        port=2205,
        hostname="bench-find",
        sudo_binary="find",
        description="NOPASSWD sudo for /usr/bin/find (GTFOBins)",
    ),
    BenchmarkTarget(
        id="sudo-less",
        name="Bench · sudo less",
        service="bench-sudo-less",
        port=2206,
        hostname="bench-less",
        sudo_binary="less",
        description="NOPASSWD sudo for /usr/bin/less (GTFOBins)",
    ),
    BenchmarkTarget(
        id="sudo-nano",
        name="Bench · sudo nano",
        service="bench-sudo-nano",
        port=2207,
        hostname="bench-nano",
        sudo_binary="nano",
        description="NOPASSWD sudo for /usr/bin/nano (GTFOBins)",
    ),
    BenchmarkTarget(
        id="sudo-python",
        name="Bench · sudo python",
        service="bench-sudo-python",
        port=2208,
        hostname="bench-python",
        sudo_binary="python3",
        description="NOPASSWD sudo for /usr/bin/python3 (GTFOBins)",
    ),
    BenchmarkTarget(
        id="sudo-tar",
        name="Bench · sudo tar",
        service="bench-sudo-tar",
        port=2209,
        hostname="bench-tar",
        sudo_binary="tar",
        description="NOPASSWD sudo for /usr/bin/tar (GTFOBins)",
    ),
    BenchmarkTarget(
        id="sudo-env",
        name="Bench · sudo env",
        service="bench-sudo-env",
        port=2210,
        hostname="bench-env",
        sudo_binary="env",
        description="NOPASSWD sudo for /usr/bin/env (GTFOBins)",
    ),
]


def list_targets() -> List[Dict[str, Any]]:
    return [t.to_dict() for t in TARGETS]


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

    # Preserve caller order; dedupe while validating.
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
