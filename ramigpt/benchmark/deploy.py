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


def _combine_process_output(stdout: str = "", stderr: str = "") -> str:
    """Merge stdout/stderr without dropping either stream."""
    parts: List[str] = []
    out = (stdout or "").strip()
    err = (stderr or "").strip()
    if out:
        parts.append(out)
    if err and err != out:
        parts.append(err)
    return "\n".join(parts).strip()


def _ansible_failure_hint(output: str) -> str:
    """Extra remediation text for common Ansible deploy failures."""
    lower = (output or "").lower()
    if "requires python 3.9" in lower or (
        "python 3.9 or newer on the target" in lower
    ):
        return (
            "Hint: the remote lab host needs Python 3.9+ for ansible-core 2.20+, "
            "or install ansible-core 2.18/2.19 on the RamiGPT host "
            "(requirements.txt pins <2.20 for Ubuntu 20.04 / Python 3.8 labs)."
        )
    if "connection plugin 'paramiko'" in lower or "connection plugin \"paramiko\"" in lower:
        return (
            "Hint: ansible-core no longer ships the paramiko connection plugin; "
            "use ansible_connection=ssh and install sshpass."
        )
    if "sshpass" in lower and ("not found" in lower or "to use the ssh" in lower):
        return "Hint: install sshpass on the RamiGPT host (apt install sshpass)."
    return ""


def _ansible_failure_summary(output: str) -> str:
    """Pull the most useful Ansible failure line(s) for UI status."""
    text = (output or "").strip()
    if not text:
        return ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # Prefer the human-readable Sub-Event / requires-Python lines when present.
    for ln in lines:
        if "requires python" in ln.lower() and "target" in ln.lower():
            return ln[:400]
    fatal = [ln for ln in lines if ln.lower().startswith("fatal:") or "[error]" in ln.lower()]
    if fatal:
        # Prefer the concrete msg= / connection-plugin line when present.
        preferred = [
            ln
            for ln in fatal
            if "connection plugin" in ln.lower()
            or "requires python" in ln.lower()
            or '"msg"' in ln
            or "msg=" in ln.lower()
            or "unreachable" in ln.lower()
        ]
        picks = preferred or fatal
        summary = picks[-1]
        # Keep short enough for the status strip but preserve the key detail.
        if len(summary) > 400:
            summary = summary[:397] + "..."
        return summary
    # Fall back to the last non-recap line.
    for ln in reversed(lines):
        if ln.startswith("PLAY RECAP") or ln.startswith("PLAY [") or ln.startswith("TASK ["):
            continue
        if ln.startswith("*$") or ln.startswith("$ "):
            continue
        return ln[:400]
    return lines[-1][:400]


def _command_failure_message(returncode: int, cmd: Sequence[str], stdout: str, stderr: str) -> str:
    """Build a UI-friendly multi-line failure for ansible-playbook / shell commands."""
    output = _combine_process_output(stdout, stderr)
    cmd_s = " ".join(cmd)
    headline = f"Command failed ({returncode}): {cmd_s}"
    if not output:
        return headline

    summary = _ansible_failure_summary(output) if "ansible-playbook" in cmd_s else ""
    hint = _ansible_failure_hint(output) if "ansible-playbook" in cmd_s else ""
    blocks = [headline]
    if summary and summary not in headline:
        blocks.insert(0, f"Ansible deploy failed: {summary}")
    if hint:
        blocks.insert(1 if summary else 0, hint)
    blocks.append(output)
    return "\n\n".join(blocks)


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
    combined = _combine_process_output(result.stdout or "", result.stderr or "")
    if combined:
        log(combined)
    if result.returncode != 0:
        raise RuntimeError(
            _command_failure_message(
                result.returncode,
                cmd,
                result.stdout or "",
                result.stderr or "",
            )
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
    from ramigpt.utils.ubuntu_requirements import ensure_ubuntu_requirements

    ensure_ubuntu_requirements(install=True, log=log)

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
    from ramigpt.utils.ubuntu_requirements import ensure_ubuntu_requirements

    # Fast path still needs OpenSSH tooling; full deploy needs sshpass + ansible.
    ensure_ubuntu_requirements(install=True, log=log, check_ansible=True)

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
