"""Deploy benchmark Docker Compose to a remote lab host via Ansible."""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from ramigpt.benchmark.targets import BENCH_PASSWORD, BENCH_USERNAME, TARGETS
from ramigpt.paths import PROJECT_ROOT
from ramigpt.utils import debug_logger

BENCHMARK_COMPOSE_DIR = PROJECT_ROOT / "docker" / "benchmark"
# Remote Linux lab: host networking (sshd binds host ports; avoids Docker DNAT blackhole).
BENCHMARK_COMPOSE_FILE = BENCHMARK_COMPOSE_DIR / "docker-compose.yml"
ANSIBLE_PLAYBOOK = PROJECT_ROOT / "ansible" / "benchmark" / "playbook.yml"

LogFn = Callable[[str], None]


def ensure_compose_assets() -> None:
    if not BENCHMARK_COMPOSE_FILE.is_file():
        raise FileNotFoundError(f"Missing benchmark compose file: {BENCHMARK_COMPOSE_FILE}")
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


def _selected_targets(targets: Optional[Sequence] = None) -> List:
    selected = list(targets) if targets is not None else list(TARGETS)
    if not selected:
        raise ValueError("At least one benchmark target is required to deploy")
    return selected


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


def deploy_remote(
    cfg: RemoteDeployConfig,
    log: LogFn = _default_log,
    targets: Optional[Sequence] = None,
) -> str:
    """
    Use Ansible to install Docker (if needed), copy compose assets, bring selected
    targets up, and verify only those SSH ports on the remote host.
    """
    ensure_compose_assets()
    selected = _selected_targets(targets)
    services = [t.service for t in selected]
    ports = [int(t.port) for t in selected]
    ansible = shutil.which("ansible-playbook")
    if not ansible:
        raise RuntimeError(
            "ansible-playbook not found. Install ansible-core (pip install ansible-core) "
            "for remote benchmark deploy."
        )

    # Pre-flight SSH so we fail fast with a clear error before Ansible.
    test_ssh_access(cfg, log=log)

    # Password auth over the ssh connection plugin needs sshpass (ansible-core no
    # longer ships the old paramiko connection plugin).
    if not shutil.which("sshpass"):
        raise RuntimeError(
            "sshpass not found. Install it for remote Ansible password auth "
            "(e.g. apt install sshpass / brew install sshpass)."
        )

    # Keep secrets out of inventory.ini (passwords may contain @ / spaces).
    inventory_body = "\n".join(
        [
            "[benchmark_hosts]",
            f"bench ansible_host={cfg.host} ansible_user={cfg.username} ansible_port={cfg.port}",
            "",
            "[all:vars]",
            "ansible_connection=ssh",
            "ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'",
            "ansible_python_interpreter=auto_silent",
            "ansible_become=true",
            "",
        ]
    )
    all_ports = sorted({int(t.port) for t in TARGETS})
    extra_vars = {
        "ansible_password": cfg.password,
        "ansible_become_password": cfg.password,
        "bench_compose_services": services,
        "bench_ssh_ports": ports,
        "bench_all_ssh_ports": all_ports,
    }
    log(
        f"Deploying {len(selected)} target(s) via Ansible: "
        f"{', '.join(t.id for t in selected)} (ports {', '.join(str(p) for p in ports)})"
    )

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

    wait_for_target_ports(cfg.host, selected, timeout=120, log=log)
    return cfg.host


def _tcp_port_open(host: str, port: int, *, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_target_ports(
    host: str,
    log: LogFn = _default_log,
    targets: Optional[Sequence] = None,
    *,
    parallel: bool = True,
) -> List[dict]:
    selected = list(targets if targets is not None else TARGETS)

    def _check_one(target) -> dict:
        open_ = _tcp_port_open(host, int(target.port))
        return {"id": target.id, "host": host, "port": target.port, "open": open_}

    if not selected:
        return []

    if parallel and len(selected) > 1:
        results_by_id: Dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=min(len(selected), 8)) as pool:
            futures = {pool.submit(_check_one, t): t for t in selected}
            for future in as_completed(futures):
                item = future.result()
                results_by_id[item["id"]] = item
        results = [results_by_id[t.id] for t in selected]
    else:
        results = [_check_one(t) for t in selected]

    for item in results:
        log(f"Port check {host}:{item['port']} → {'open' if item['open'] else 'closed'}")
    return results


def _probe_target_ssh(host: str, target, *, log: LogFn = _default_log) -> bool:
    """Verify lowpriv SSH login on a benchmark target port."""
    try:
        from pwn import ssh as pwn_ssh
    except Exception as exc:  # noqa: BLE001
        log(f"SSH probe {host}:{target.port} ({target.id}): pwntools unavailable ({exc})")
        return False

    conn = None
    try:
        conn = pwn_ssh(
            user=BENCH_USERNAME,
            host=host,
            port=int(target.port),
            password=BENCH_PASSWORD,
            timeout=10,
            ignore_config=True,
        )
        tube = conn.run("id -u && whoami", timeout=10)
        if tube is None:
            log(f"SSH probe {host}:{target.port} ({target.id}): no shell")
            return False
        out = tube.recvall(timeout=10).decode(errors="replace").strip().splitlines()
        if len(out) < 2:
            log(f"SSH probe {host}:{target.port} ({target.id}): unexpected output {out!r}")
            return False
        uid, user = out[0].strip(), out[-1].strip()
        ok = uid != "0" and user == BENCH_USERNAME
        if not ok:
            log(
                f"SSH probe {host}:{target.port} ({target.id}): "
                f"expected {BENCH_USERNAME} (non-root), got uid={uid} user={user}"
            )
        return ok
    except Exception as exc:  # noqa: BLE001
        log(f"SSH probe {host}:{target.port} ({target.id}) failed: {exc}")
        return False
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass


def verify_targets_ssh(
    host: str,
    targets: Sequence,
    log: LogFn = _default_log,
    *,
    parallel: bool = True,
) -> Tuple[bool, List[str]]:
    """Return (all_ok, list of target ids that failed SSH probe)."""
    selected = list(targets)
    if not selected:
        return True, []

    failed: List[str] = []

    def _probe(target) -> Tuple[str, bool]:
        return target.id, _probe_target_ssh(host, target, log=log)

    if parallel and len(selected) > 1:
        with ThreadPoolExecutor(max_workers=min(len(selected), 8)) as pool:
            for target_id, ok in pool.map(_probe, selected):
                if not ok:
                    failed.append(target_id)
    else:
        for target in selected:
            _, ok = _probe(target)
            if not ok:
                failed.append(target.id)

    if failed:
        return False, failed
    log(f"SSH OK on all {len(selected)} target port(s) as {BENCH_USERNAME}")
    return True, []


def ensure_remote_benchmark(
    cfg: RemoteDeployConfig,
    log: LogFn = _default_log,
    targets: Optional[Sequence] = None,
    *,
    force_deploy: bool = False,
) -> str:
    """
    Bring benchmark targets online on the remote lab host.

    Fast path: when every selected SSH port is open and accepts lowpriv login,
    skip Ansible entirely. Otherwise run the full playbook deploy.
    """
    selected = _selected_targets(targets)
    host = cfg.host

    if not force_deploy:
        ports = check_target_ports(host, log=log, targets=selected)
        if all(p["open"] for p in ports):
            log(
                f"All {len(selected)} target port(s) open on {host} — "
                f"verifying benchmark SSH ({', '.join(t.id for t in selected)})"
            )
            ready, failed = verify_targets_ssh(host, selected, log=log)
            if ready:
                log(f"Benchmark targets ready on {host} — skipping Ansible deploy")
                return host
            log(f"SSH verify failed for {', '.join(failed)} — running full deploy")
        else:
            missing = [str(p["port"]) for p in ports if not p["open"]]
            log(f"Closed port(s) on {host}: {', '.join(missing)} — running Ansible deploy")

    return deploy_remote(cfg, log=log, targets=selected)


def all_target_ports_open(
    host: str,
    log: LogFn = _default_log,
    targets: Optional[Sequence] = None,
) -> bool:
    """True when every given (or all) benchmark target SSH port accepts connections."""
    results = check_target_ports(host, log=log, targets=targets)
    return bool(results) and all(p["open"] for p in results)
