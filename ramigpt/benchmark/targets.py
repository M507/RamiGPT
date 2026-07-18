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
FAMILY_CREDENTIALS = "credentials"
FAMILY_PATH = "path"


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


@dataclass(frozen=True)
class BenchmarkProfile:
    """Named target selection exposed by the benchmark UI."""

    id: str
    name: str
    description: str
    target_ids: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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
    # ----- easy backlog batch -----
    _t(
        id="sudo-all",
        name="Bench · sudo ALL",
        service="bench-sudo-all",
        port=2170,
        hostname="bench-sudo-all",
        family=FAMILY_SUDO_ADVANCED,
        primitive="ALL",
        description="NOPASSWD sudo ALL (unrestricted)",
        misconfig="sudo-all",
    ),
    _t(
        id="sudo-group",
        name="Bench · sudo group",
        service="bench-sudo-group",
        port=2171,
        hostname="bench-sudo-group",
        family=FAMILY_SUDO_ADVANCED,
        primitive="%benchsudo",
        description="NOPASSWD sudo via group membership",
        misconfig="sudo-group",
    ),
    _t(
        id="sudo-writable-script",
        name="Bench · sudo writable script",
        service="bench-sudo-writable-script",
        port=2172,
        hostname="bench-sudo-writable-script",
        family=FAMILY_SUDO_ADVANCED,
        primitive="/opt/bench/root.sh",
        description="NOPASSWD sudo for world-writable script",
        misconfig="sudo-writable-script",
    ),
    _t(
        id="sudo-pythonpath",
        name="Bench · sudo PYTHONPATH",
        service="bench-sudo-pythonpath",
        port=2173,
        hostname="bench-sudo-pythonpath",
        family=FAMILY_SUDO_ADVANCED,
        primitive="PYTHONPATH",
        description="env_keep PYTHONPATH + NOPASSWD python3",
        misconfig="sudo-pythonpath",
    ),
    _t(
        id="writable-shadow",
        name="Bench · writable shadow",
        service="bench-writable-shadow",
        port=2174,
        hostname="bench-writable-shadow",
        family=FAMILY_WRITABLE,
        primitive="/etc/shadow",
        description="World-writable /etc/shadow",
        misconfig="writable:shadow",
    ),
    _t(
        id="writable-sudoers",
        name="Bench · writable sudoers.d",
        service="bench-writable-sudoers",
        port=2175,
        hostname="bench-writable-sudoers",
        family=FAMILY_WRITABLE,
        primitive="/opt/bench/sudoers.pending",
        description="Writable pending sudoers file installed by root poller",
        misconfig="writable:sudoers",
    ),
    _t(
        id="suid-writable",
        name="Bench · writable SUID binary",
        service="bench-suid-writable",
        port=2176,
        hostname="bench-suid-writable",
        family=FAMILY_SUID,
        primitive="/opt/bench/suidbin",
        description="World-writable SUID binary (overwrite payload)",
        misconfig="suid-writable",
    ),
    _t(
        id="cap-dac-read",
        name="Bench · cap_dac_read_search",
        service="bench-cap-dac-read",
        port=2228,
        hostname="bench-cap-dac-read",
        family=FAMILY_CAPABILITIES,
        primitive="python3",
        description="cap_dac_read_search+ep on python3 (read any file)",
        misconfig="cap-dac-read:python3",
    ),
    _t(
        id="writable-root-ssh",
        name="Bench · writable root authorized_keys",
        service="bench-writable-root-ssh",
        port=2229,
        hostname="bench-writable-root-ssh",
        family=FAMILY_WRITABLE,
        primitive="/root/.ssh/authorized_keys",
        description="World-writable /root/.ssh/authorized_keys (dirs traversable)",
        misconfig="writable:root-ssh",
    ),
    _t(
        id="cred-root-key",
        name="Bench · readable root SSH key",
        service="bench-cred-root-key",
        port=2230,
        hostname="bench-cred-root-key",
        family=FAMILY_CREDENTIALS,
        primitive="root_id_rsa",
        description="World-readable private key for root SSH",
        misconfig="cred-root-key",
    ),
    _t(
        id="cred-cleartext",
        name="Bench · cleartext root password",
        service="bench-cred-cleartext",
        port=2177,
        hostname="bench-cred-cleartext",
        family=FAMILY_CREDENTIALS,
        primitive="credentials.txt",
        description="Root password in world-readable file",
        misconfig="cred-cleartext",
    ),
    _t(
        id="path-hijack",
        name="Bench · PATH hijack",
        service="bench-path-hijack",
        port=2232,
        hostname="bench-path-hijack",
        family=FAMILY_PATH,
        primitive="/opt/pathhijack",
        description="Root runs relative command with attacker-writable PATH dir",
        misconfig="path-hijack",
    ),
    _t(
        id="sudo-noauth",
        name="Bench · sudo !authenticate",
        service="bench-sudo-noauth",
        port=2233,
        hostname="bench-sudo-noauth",
        family=FAMILY_SUDO_ADVANCED,
        primitive="!authenticate",
        description="Defaults !authenticate for lowpriv (no password)",
        misconfig="sudo-noauth",
    ),
    _t(
        id="cred-history",
        name="Bench · bash_history password",
        service="bench-cred-history",
        port=2178,
        hostname="bench-cred-history",
        family=FAMILY_CREDENTIALS,
        primitive=".bash_history",
        description="Root password leaked in .bash_history",
        misconfig="cred-history",
    ),
    _t(
        id="sudo-bash",
        name="Bench · sudo bash",
        service="bench-sudo-bash",
        port=2179,
        hostname="bench-sudo-bash",
        family=FAMILY_SUDO,
        primitive="bash",
        description="NOPASSWD sudo for /bin/bash",
        misconfig="sudo:/bin/bash",
    ),
    _t(
        id="cap-chown",
        name="Bench · cap_chown",
        service="bench-cap-chown",
        port=2180,
        hostname="bench-cap-chown",
        family=FAMILY_CAPABILITIES,
        primitive="python3",
        description="cap_chown+ep on python3 (steal ownership of any file)",
        misconfig="cap-chown:python3",
    ),
    _t(
        id="writable-lib",
        name="Bench · writable lib dir",
        service="bench-writable-lib",
        port=2237,
        hostname="bench-writable-lib",
        family=FAMILY_WRITABLE,
        primitive="/usr/local/lib/benchhijack",
        description="World-writable lib dir loaded by root poller",
        misconfig="writable:lib",
    ),
    _t(
        id="python-cwd",
        name="Bench · python cwd hijack",
        service="bench-python-cwd",
        port=2238,
        hostname="bench-python-cwd",
        family=FAMILY_PYTHON,
        primitive="cwd",
        description="Root python job imports from writable cwd",
        misconfig="python-cwd",
    ),
    _t(
        id="cred-ansible",
        name="Bench · ansible secrets",
        service="bench-cred-ansible",
        port=2239,
        hostname="bench-cred-ansible",
        family=FAMILY_CREDENTIALS,
        primitive="ansible",
        description="World-readable Ansible vault/group_vars with root password",
        misconfig="cred-ansible",
    ),
    _t(
        id="cred-adm-log",
        name="Bench · adm log credentials",
        service="bench-cred-adm-log",
        port=2181,
        hostname="bench-cred-adm-log",
        family=FAMILY_CREDENTIALS,
        primitive="adm",
        description="adm group can read planted password in logs",
        misconfig="cred-adm-log",
    ),
    _t(
        id="writable-ld-so-preload",
        name="Bench · writable ld.so.preload",
        service="bench-writable-ld-so-preload",
        port=2182,
        hostname="bench-writable-ld-so-preload",
        family=FAMILY_WRITABLE,
        primitive="/etc/ld.so.preload",
        description="World-writable ld.so.preload + root exec trigger",
        misconfig="writable:ld-so-preload",
    ),
]


def _target_ids(*families: str) -> List[str]:
    selected = set(families)
    return [target.id for target in TARGETS if target.family in selected]


PROFILES: List[BenchmarkProfile] = [
    BenchmarkProfile(
        id="does-it-work",
        name="Does it work?",
        description="Quick smoke test: sudo vim, sudo ALL, and sudo awk",
        target_ids=["sudo-vim", "sudo-all", "sudo-awk"],
    ),
    BenchmarkProfile(
        id="all-sudo-problems",
        name="All sudo problems",
        description="Every classic and advanced sudo misconfiguration",
        target_ids=_target_ids(FAMILY_SUDO, FAMILY_SUDO_ADVANCED),
    ),
    BenchmarkProfile(
        id="classic-sudo",
        name="Classic sudo commands",
        description="NOPASSWD command and GTFOBins-style sudo targets",
        target_ids=_target_ids(FAMILY_SUDO),
    ),
    BenchmarkProfile(
        id="advanced-sudo",
        name="Advanced sudo configuration",
        description="Environment, group, script, and authentication sudo issues",
        target_ids=_target_ids(FAMILY_SUDO_ADVANCED),
    ),
    BenchmarkProfile(
        id="suid",
        name="SUID binaries",
        description="Unsafe and writable SUID executables",
        target_ids=_target_ids(FAMILY_SUID),
    ),
    BenchmarkProfile(
        id="writable",
        name="Writable files and loaders",
        description="Writable system files, root jobs, keys, and loader paths",
        target_ids=_target_ids(FAMILY_WRITABLE),
    ),
    BenchmarkProfile(
        id="capabilities",
        name="Linux capabilities",
        description="Dangerous file capabilities on interpreters",
        target_ids=_target_ids(FAMILY_CAPABILITIES),
    ),
    BenchmarkProfile(
        id="python-path",
        name="Python and PATH hijacks",
        description="Python import-path and executable PATH attacks",
        target_ids=_target_ids(FAMILY_PYTHON, FAMILY_PATH),
    ),
    BenchmarkProfile(
        id="credentials",
        name="Credential leaks",
        description="Keys, passwords, history, Ansible data, and logs",
        target_ids=_target_ids(FAMILY_CREDENTIALS),
    ),
    BenchmarkProfile(
        id="nfs",
        name="NFS detection",
        description="Detect-only NFS no_root_squash target",
        target_ids=_target_ids(FAMILY_NFS),
    ),
]


def list_targets() -> List[Dict[str, Any]]:
    return [t.to_dict() for t in TARGETS]


def list_profiles() -> List[Dict[str, Any]]:
    return [profile.to_dict() for profile in PROFILES]


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

    None means all targets. An empty list means no targets (caller validates).
    Unknown ids raise ValueError.
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
        return []

    known = {t.id: t for t in TARGETS}
    missing = [tid for tid in ordered if tid not in known]
    if missing:
        raise ValueError(f"Unknown benchmark target id(s): {', '.join(missing)}")
    return [known[tid] for tid in ordered]
