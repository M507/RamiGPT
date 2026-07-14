"""Deploy benchmark Docker Compose locally or via Ansible on a remote host."""

from __future__ import annotations

import shutil
import socket
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Sequence

from ramigpt.benchmark.targets import TARGETS
from ramigpt.paths import PROJECT_ROOT
from ramigpt.utils import debug_logger

BENCHMARK_COMPOSE_DIR = PROJECT_ROOT / "docker" / "benchmark"
BENCHMARK_COMPOSE_FILE = BENCHMARK_COMPOSE_DIR / "docker-compose.yml"
ANSIBLE_PLAYBOOK = PROJECT_ROOT / "ansible" / "benchmark" / "playbook.yml"

LogFn = Callable[[str], None]


@dataclass
class RemoteDeployConfig:
    host: str
    username: str
    password: str
    port: int = 22


def _default_log(message: str) -> None:
    debug_logger.info(message)


def _run(
    cmd: Sequence[str],
    *,
    cwd: Optional[Path] = None,
    env: Optional[dict] = None,
    log: LogFn = _default_log,
    timeout: Optional[int] = None,
) -> subprocess.CompletedProcess:
    log(f"$ {' '.join(cmd)}")
    result = subprocess.run(
        list(cmd),
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.stdout.strip():
        log(result.stdout.strip())
    if result.stderr.strip():
        log(result.stderr.strip())
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n{result.stderr or result.stdout}"
        )
    return result


def wait_for_tcp(host: str, port: int, timeout: float = 90.0, log: LogFn = _default_log) -> None:
    """Block until TCP port accepts connections (or raise)."""
    import time

    deadline = time.time() + timeout
    last_err: Optional[Exception] = None
    log(f"Waiting for {host}:{port} …")
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2.0):
                log(f"Port {host}:{port} is open")
                return
        except OSError as exc:
            last_err = exc
            time.sleep(1.0)
    raise TimeoutError(f"Timed out waiting for {host}:{port}: {last_err}")


def ensure_compose_assets() -> None:
    if not BENCHMARK_COMPOSE_FILE.is_file():
        raise FileNotFoundError(f"Missing benchmark compose file: {BENCHMARK_COMPOSE_FILE}")
    if not ANSIBLE_PLAYBOOK.is_file():
        raise FileNotFoundError(f"Missing Ansible playbook: {ANSIBLE_PLAYBOOK}")


def deploy_local(log: LogFn = _default_log) -> str:
    """Build and start benchmark containers on this machine. Returns host IP."""
    ensure_compose_assets()
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("docker CLI not found on PATH (required for local benchmark deploy)")
    _run(
        [docker, "compose", "-f", str(BENCHMARK_COMPOSE_FILE), "up", "-d", "--build"],
        cwd=BENCHMARK_COMPOSE_DIR,
        log=log,
        timeout=600,
    )
    host = "127.0.0.1"
    for target in TARGETS:
        wait_for_tcp(host, target.port, timeout=120, log=log)
    return host


def tear_down_local(log: LogFn = _default_log) -> None:
    docker = shutil.which("docker")
    if not docker or not BENCHMARK_COMPOSE_FILE.is_file():
        return
    try:
        _run(
            [docker, "compose", "-f", str(BENCHMARK_COMPOSE_FILE), "down"],
            cwd=BENCHMARK_COMPOSE_DIR,
            log=log,
            timeout=120,
        )
    except Exception as exc:  # noqa: BLE001 — teardown is best-effort
        log(f"Local teardown warning: {exc}")


def deploy_remote(cfg: RemoteDeployConfig, log: LogFn = _default_log) -> str:
    """
    Use Ansible to install Docker (if needed), copy compose assets, bring targets up,
    and verify ports 2201/2202 on the remote host.
    """
    ensure_compose_assets()
    ansible = shutil.which("ansible-playbook")
    if not ansible:
        raise RuntimeError(
            "ansible-playbook not found. Install ansible-core (pip install ansible-core) "
            "for remote benchmark deploy."
        )

    inventory_body = "\n".join(
        [
            "[benchmark_hosts]",
            (
                f"bench ansible_host={cfg.host} ansible_user={cfg.username} "
                f"ansible_password={cfg.password} ansible_port={cfg.port}"
            ),
            "",
            "[all:vars]",
            "ansible_connection=ssh",
            "ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'",
            "ansible_python_interpreter=auto_silent",
            "ansible_become=true",
            f"ansible_become_password={cfg.password}",
            "",
        ]
    )

    with tempfile.TemporaryDirectory(prefix="ramigpt-bench-") as tmp:
        inv_path = Path(tmp) / "inventory.ini"
        inv_path.write_text(inventory_body, encoding="utf-8")
        log(f"Running Ansible playbook against {cfg.host}:{cfg.port} as {cfg.username}")
        _run(
            [
                ansible,
                "-i",
                str(inv_path),
                str(ANSIBLE_PLAYBOOK),
            ],
            cwd=PROJECT_ROOT,
            log=log,
            timeout=900,
        )

    for target in TARGETS:
        wait_for_tcp(cfg.host, target.port, timeout=120, log=log)
    return cfg.host


def check_target_ports(host: str, log: LogFn = _default_log) -> List[dict]:
    results = []
    for target in TARGETS:
        open_ = False
        try:
            with socket.create_connection((host, target.port), timeout=2.0):
                open_ = True
        except OSError:
            open_ = False
        results.append({"id": target.id, "host": host, "port": target.port, "open": open_})
        log(f"Port check {host}:{target.port} → {'open' if open_ else 'closed'}")
    return results
