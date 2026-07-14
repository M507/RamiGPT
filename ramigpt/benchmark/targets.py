"""Privilege-escalation benchmark suite definitions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List


# Shared login for every benchmark SSH target (ports 2201–2299).
BENCH_USERNAME = "zeus"
BENCH_PASSWORD = "benchmark"
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
        port=2201,
        hostname="bench-vim",
        sudo_binary="vim",
        description="NOPASSWD sudo for /usr/bin/vim (GTFOBins)",
    ),
    BenchmarkTarget(
        id="sudo-awk",
        name="Bench · sudo awk",
        service="bench-sudo-awk",
        port=2202,
        hostname="bench-awk",
        sudo_binary="awk",
        description="NOPASSWD sudo for /usr/bin/awk (GTFOBins)",
    ),
]


def list_targets() -> List[Dict[str, Any]]:
    return [t.to_dict() for t in TARGETS]


def get_target(target_id: str) -> BenchmarkTarget:
    for target in TARGETS:
        if target.id == target_id:
            return target
    raise KeyError(f"Unknown benchmark target: {target_id}")
