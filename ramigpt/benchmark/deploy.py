"""Deploy benchmark Docker Compose locally or via Ansible on a remote host."""

from __future__ import annotations

import shutil
import socket
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import json
import sys

from ramigpt.benchmark.targets import TARGETS
from ramigpt.paths import PROJECT_ROOT
from ramigpt.utils import debug_logger

BENCHMARK_COMPOSE_DIR = PROJECT_ROOT / "docker" / "benchmark"
# Remote Linux lab: host networking (sshd binds host ports; avoids Docker DNAT blackhole).
BENCHMARK_COMPOSE_FILE = BENCHMARK_COMPOSE_DIR / "docker-compose.yml"
# Local Docker Desktop (Mac/Windows): bridge publish (host network is unsupported).
BENCHMARK_COMPOSE_LOCAL_FILE = BENCHMARK_COMPOSE_DIR / "docker-compose.local.yml"
ANSIBLE_PLAYBOOK = PROJECT_ROOT / "ansible" / "benchmark" / "playbook.yml"

LogFn = Callable[[str], None]


def local_compose_file() -> Path:
    """Compose file for deploy_local based on the RamiGPT host OS."""
    if sys.platform.startswith("linux"):
        return BENCHMARK_COMPOSE_FILE
    return BENCHMARK_COMPOSE_LOCAL_FILE


def ensure_compose_assets() -> None:
    if not BENCHMARK_COMPOSE_FILE.is_file():
        raise FileNotFoundError(f"Missing benchmark compose file: {BENCHMARK_COMPOSE_FILE}")
    if not BENCHMARK_COMPOSE_LOCAL_FILE.is_file():
        raise FileNotFoundError(
            f"Missing local benchmark compose file: {BENCHMARK_COMPOSE_LOCAL_FILE}"
        )
    if not ANSIBLE_PLAYBOOK.is_file():
        raise FileNotFoundError(f"Missing Ansible playbook: {ANSIBLE_PLAYBOOK}")


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


def deploy_local(log: LogFn = _default_log) -> str:
    """Build and start benchmark containers on this machine. Returns host IP."""
    ensure_compose_assets()
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("docker CLI not found on PATH (required for local benchmark deploy)")
    compose = local_compose_file()
    log(f"Local compose file: {compose.name}")
    # Tear down either stack so a prior host/bridge deploy does not leave stale listeners.
    for path in {compose, BENCHMARK_COMPOSE_FILE, BENCHMARK_COMPOSE_LOCAL_FILE}:
        try:
            _run(
                [
                    docker,
                    "compose",
                    "-f",
                    str(path),
                    "down",
                    "--remove-orphans",
                ],
                cwd=BENCHMARK_COMPOSE_DIR,
                log=log,
                timeout=120,
            )
        except Exception as exc:  # noqa: BLE001 — prior stack may be absent
            log(f"Compose down {path.name} (best-effort): {exc}")
    _run(
        [
            docker,
            "compose",
            "-f",
            str(compose),
            "up",
            "-d",
            "--build",
            "--force-recreate",
        ],
        cwd=BENCHMARK_COMPOSE_DIR,
        log=log,
        timeout=600,
    )
    host = "127.0.0.1"
    for target in TARGETS:
        wait_for_tcp(host, target.port, timeout=120, log=log)
    return host


def wait_for_target_ports(
    host: str,
    targets: Sequence = TARGETS,
    *,
    timeout: float = 120.0,
    log: LogFn = _default_log,
) -> None:
    """Wait until each given target's SSH port accepts connections."""
    for target in targets:
        wait_for_tcp(host, int(target.port), timeout=timeout, log=log)


def tear_down_local(log: LogFn = _default_log) -> None:
    docker = shutil.which("docker")
    if not docker:
        return
    for path in (BENCHMARK_COMPOSE_FILE, BENCHMARK_COMPOSE_LOCAL_FILE):
        if not path.is_file():
            continue
        try:
            _run(
                [docker, "compose", "-f", str(path), "down", "--remove-orphans"],
                cwd=BENCHMARK_COMPOSE_DIR,
                log=log,
                timeout=120,
            )
        except Exception as exc:  # noqa: BLE001 — teardown is best-effort
            log(f"Local teardown warning ({path.name}): {exc}")


def test_ssh_access(cfg: RemoteDeployConfig, log: LogFn = _default_log) -> Dict[str, Any]:
    """Verify SSH login to the remote lab host (pre-flight before Ansible)."""
    try:
        from pwn import ssh as pwn_ssh
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"pwntools SSH unavailable: {exc}") from exc

    log(f"Testing SSH {cfg.username}@{cfg.host}:{cfg.port}")
    conn = pwn_ssh(
        user=cfg.username,
        host=cfg.host,
        port=int(cfg.port),
        password=cfg.password,
        timeout=15,
        ignore_config=True,
    )
    try:
        tube = conn.run("id && hostname && uname -srm", timeout=15)
        if tube is None:
            raise RuntimeError("ssh.run() returned None during pre-flight")
        out = tube.recvall(timeout=15)
        text = out.decode(errors="replace").strip()
        log(f"SSH OK:\n{text}")
        return {
            "ok": True,
            "host": cfg.host,
            "port": cfg.port,
            "username": cfg.username,
            "output": text,
        }
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


def deploy_remote(cfg: RemoteDeployConfig, log: LogFn = _default_log) -> str:
    """
    Use Ansible to install Docker (if needed), copy compose assets, bring targets up,
    and verify benchmark SSH ports on the remote host.
    """
    ensure_compose_assets()
    ansible = shutil.which("ansible-playbook")
    if not ansible:
        raise RuntimeError(
            "ansible-playbook not found. Install ansible-core (pip install ansible-core) "
            "for remote benchmark deploy."
        )

    # Pre-flight SSH so we fail fast with a clear error before Ansible.
    test_ssh_access(cfg, log=log)

    # Keep secrets out of inventory.ini (passwords may contain @ / spaces).
    inventory_body = "\n".join(
        [
            "[benchmark_hosts]",
            f"bench ansible_host={cfg.host} ansible_user={cfg.username} ansible_port={cfg.port}",
            "",
            "[all:vars]",
            "ansible_connection=paramiko",
            "ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'",
            "ansible_python_interpreter=auto_silent",
            "ansible_become=true",
            "",
        ]
    )
    extra_vars = {
        "ansible_password": cfg.password,
        "ansible_become_password": cfg.password,
    }

    with tempfile.TemporaryDirectory(prefix="ramigpt-bench-") as tmp:
        inv_path = Path(tmp) / "inventory.ini"
        vars_path = Path(tmp) / "extra_vars.json"
        inv_path.write_text(inventory_body, encoding="utf-8")
        vars_path.write_text(json.dumps(extra_vars), encoding="utf-8")
        log(f"Running Ansible playbook against {cfg.host}:{cfg.port} as {cfg.username}")
        _run(
            [
                ansible,
                "-i",
                str(inv_path),
                str(ANSIBLE_PLAYBOOK),
                "-e",
                f"@{vars_path}",
            ],
            cwd=PROJECT_ROOT,
            log=log,
            timeout=900,
        )

    wait_for_target_ports(cfg.host, TARGETS, timeout=120, log=log)
    return cfg.host


def check_target_ports(
    host: str,
    log: LogFn = _default_log,
    targets: Optional[Sequence] = None,
) -> List[dict]:
    results = []
    for target in targets if targets is not None else TARGETS:
        open_ = False
        try:
            with socket.create_connection((host, target.port), timeout=2.0):
                open_ = True
        except OSError:
            open_ = False
        results.append({"id": target.id, "host": host, "port": target.port, "open": open_})
        log(f"Port check {host}:{target.port} → {'open' if open_ else 'closed'}")
    return results


def all_target_ports_open(
    host: str,
    log: LogFn = _default_log,
    targets: Optional[Sequence] = None,
) -> bool:
    """True when every given (or all) benchmark target SSH port accepts connections."""
    results = check_target_ports(host, log=log, targets=targets)
    return bool(results) and all(p["open"] for p in results)
