"""Classify BeRoot scan output for a benchmark target."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from ramigpt.benchmark.targets import (
    FAMILY_CAPABILITIES,
    FAMILY_CREDENTIALS,
    FAMILY_DOAS,
    FAMILY_NFS,
    FAMILY_PATH,
    FAMILY_PYTHON,
    FAMILY_SERVICES,
    FAMILY_SGID,
    FAMILY_SHELL,
    FAMILY_SUID,
    FAMILY_SUDO,
    FAMILY_SUDO_ADVANCED,
    FAMILY_WRITABLE,
    BenchmarkTarget,
)

SECTION_RE = re.compile(r"^################ (.+?) ################\s*$", re.MULTILINE)

ENV_KEEP_SUDO_IDS = frozenset(
    {
        "sudo-bash-env",
        "sudo-perl5lib",
        "sudo-ld-library-path",
        "sudo-nodepath",
        "sudo-pythonpath",
        "sudo-rubylib",
        "sudo-ps4",
        "sudo-shelopts",
    }
)

WRITABLE_HOOK_SUDO_IDS = frozenset(
    {
        "sudo-writable-script",
        "sudo-git-hook",
        "sudo-backup",
        "sudo-ansible",
        "sudo-composer",
        "sudo-pip",
        "sudo-gem",
        "sudo-npm",
        "sudo-yarn",
        "sudo-wildcard-tar",
        "sudo-mv",
        "sudo-runas",
        "sudo-noauth",
        "sudo-group",
    }
)

_BIN_PRIMITIVES = frozenset({"bash", "cp", "chmod", "dd", "sed", "mv"})

SUDO_EXTRA_BINS: dict[str, tuple[str, ...]] = {
    "sudo-backup": ("/opt/bench/backup.sh",),
    "sudo-wildcard-tar": ("/opt/bench/backup.sh",),
    "sudo-yarn": ("/usr/local/bin/yarn",),
}

WRITABLE_FALLBACK_NEEDLES: dict[str, tuple[str, ...]] = {
    "wildcard-cron": ("/opt/bench/wildcard",),
    "writable-rsyslog": ("/etc/rsyslog.d",),
    "writable-logrotate-d": ("/etc/logrotate.d",),
    "writable-systemd-dropin": ("/etc/systemd/system/bench.service.d",),
    "writable-shm-hook": ("/dev/shm/bench",),
    "writable-tmp-hook": ("/tmp/bench",),
    "writable-supervisor": ("/etc/supervisor/conf.d",),
    "writable-udev-rules": ("/etc/udev/rules.d",),
    "sudo-wildcard-tar": ("/opt/bench/tarwild",),
    "sudo-backup": ("/opt/bench/tarwild",),
}

LD_PRELOAD_SUDO_IDS = frozenset({"sudo-ld-preload", "sudo-ld-library-path"})


@dataclass(frozen=True)
class Classification:
    verdict: str
    note: str
    check: str = ""


def parse_sections(output: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    matches = list(SECTION_RE.finditer(output))
    for idx, match in enumerate(matches):
        name = match.group(1).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(output)
        sections[name] = output[start:end].strip()
    return sections


def _section(sections: dict[str, str], *names: str) -> str:
    for name in names:
        if name in sections:
            return sections[name]
    return ""


def _contains_any(text: str, needles: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(n.lower() in lowered for n in needles if n)


def _sudo_bins(target: BenchmarkTarget) -> List[str]:
    bins: List[str] = []
    mis = target.misconfig or ""
    if mis.startswith("sudo:"):
        bins.append(mis.split(":", 1)[1])
    elif mis.startswith("sudo-ld-preload:"):
        bins.append(mis.split(":", 1)[1])
    prim = target.primitive or ""
    if prim.startswith("/"):
        bins.append(prim)
    elif prim and prim.upper() == prim and prim not in {"ALL"}:
        pass
    elif prim and "/" not in prim and "+" not in prim:
        bins.append(f"/usr/bin/{prim}")
        bins.append(f"/usr/local/bin/{prim}")
        if prim in _BIN_PRIMITIVES:
            bins.append(f"/bin/{prim}")
    extras = SUDO_EXTRA_BINS.get(target.id, ())
    bins.extend(extras)
    return bins


def _classify_sudo(target: BenchmarkTarget, output: str, sections: dict[str, str]) -> Classification:
    tid = target.id
    file_perm = _section(sections, "Interesting files with write access")
    path_dirs = _section(sections, "Writable PATH / hook directories")
    sudo_rules = _section(sections, "Sudo rules", "Sudoers file")
    sudo_capture = _section(sections, "sudo -l (runner capture)")
    sudo_text = "\n".join(x for x in (sudo_rules, sudo_capture, output) if x)
    ldpreload = _section(sections, "LD_PRELOAD")
    env_keep = _section(sections, "Sudo env_keep")
    bins = _sudo_bins(target)
    has_rule = _sudo_rule_hits(sudo_text, bins)
    has_ld = "directive found" in ldpreload.lower()
    prim = target.primitive or ""

    if tid in ENV_KEEP_SUDO_IDS:
        env_signal = bool(prim and prim.upper() in env_keep.upper())
        if has_rule and env_signal:
            return Classification(
                "Yes",
                _snippet(env_keep + " | " + sudo_text),
                "env_keep + sudo_list",
            )
        return Classification("No", "env_keep directive not matched")

    if tid in LD_PRELOAD_SUDO_IDS:
        if has_ld and has_rule:
            return Classification(
                "Yes",
                _snippet(ldpreload + " | " + sudo_text),
                "ldpreload + sudo_list",
            )
        return Classification("No", "no sudo / LD_PRELOAD signal")

    if tid in WRITABLE_HOOK_SUDO_IDS:
        writable = (
            _writable_hits(file_perm, prim)
            or _writable_hits(path_dirs, prim)
            or _writable_target_hits(file_perm, target)
            or _writable_target_hits(path_dirs, target)
        )
        if has_rule and writable:
            return Classification(
                "Yes",
                _snippet((file_perm or path_dirs) + " | " + sudo_text),
                "file_permissions + sudo_list",
            )
        return Classification("No", "writable hook/script path not flagged")

    if tid == "sudo-all":
        if _contains_any(sudo_text, ("(ALL) ALL", "(ALL : ALL) ALL", "NOPASSWD: ALL")):
            return Classification("Yes", _snippet(sudo_text), "sudo_list")
        return Classification("No", "no ALL sudo rule")

    if tid == "sudo-u-hash":
        return Classification("No", "CVE-2019-14287 not checked")

    if tid == "sudo-version-detect-only":
        return Classification("No", "no sudo -V / CVE check")

    if has_rule:
        return Classification("Yes", _snippet(sudo_text), "sudo_list")
    return Classification("No", "no matching sudo rule")


def _sudo_rule_hits(output: str, bins: Sequence[str]) -> bool:
    if not bins:
        return _contains_any(
            output,
            ("NOPASSWD", "may run the following commands", "(ALL) ALL", "(ALL : ALL) ALL"),
        )
    return _contains_any(output, bins)


def _writable_hits(section: str, path: str) -> bool:
    if not section or not path:
        return False
    path = path.rstrip("*").rstrip("/")
    if path in section:
        return True
    base = path.rsplit("/", 1)[-1].rstrip("*")
    if base and base in section and "writable" in section.lower():
        return True
    return False


def _writable_target_hits(section: str, target: BenchmarkTarget) -> bool:
    prim = target.primitive or ""
    needles: List[str] = []
    if prim.startswith("/"):
        needles.append(prim)
    needles.extend(WRITABLE_FALLBACK_NEEDLES.get(target.id, ()))
    return any(_writable_hits(section, needle) for needle in needles)


def _snippet(text: str, limit: int = 160, prefer: tuple[str, ...] | None = None) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if prefer:
        preferred = [
            ln for ln in lines if any(p.lower() in ln.lower() for p in prefer)
        ]
        if preferred:
            lines = preferred + [ln for ln in lines if ln not in preferred]
    one_line = " | ".join(lines)
    return one_line[:limit]


def _capability_hits(section: str, binary: str) -> bool:
    if not section or not binary:
        return False
    pat = re.compile(rf"{re.escape(binary)}\b.*cap_", re.IGNORECASE)
    return bool(pat.search(section.replace("\n", " ")))


_SUID_ALIASES = {
    "cp": ("gnucp", "cp"),
    "python3": ("python3", "python"),
    "python": ("python3", "python"),
    "gawk": ("gawk", "awk"),
    "awk": ("gawk", "awk"),
    "hd": ("hd", "hexdump"),
    "hexdump": ("hd", "hexdump"),
    "node": ("node", "nodejs"),
    "strings": ("strings",),
}


def _suid_lab_hit(target: BenchmarkTarget, section: str) -> bool:
    if not section:
        return False

    path_lines = []
    path_bases = []
    for line in section.splitlines():
        token = line.strip().split()[0] if line.strip() else ""
        if token.startswith("/"):
            path_lines.append(token)
            path_bases.append(token.rsplit("/", 1)[-1].lower())
            if "/opt/bench/" in token:
                return True

    mis = target.misconfig or ""
    names: List[str] = []
    if mis.startswith("suid:"):
        names.append(mis.split(":", 1)[1])
    prim = (target.primitive or "").strip()
    if prim.startswith("/"):
        if any(prim in p or p.startswith(prim) for p in path_lines):
            return True
        names.append(prim.rsplit("/", 1)[-1])
    elif prim and " " not in prim and "/" not in prim:
        names.append(prim)

    for name in names:
        aliases = _SUID_ALIASES.get(name, (name,))
        for alias in aliases:
            alias_l = alias.lower()
            for base in path_bases:
                if (
                    base == alias_l
                    or base.startswith(alias_l + ".")
                    or base.endswith("-" + alias_l)
                    or base.endswith("_" + alias_l)
                    or alias_l in base.split("-")
                ):
                    return True
    return False


def classify_beroot_output(target: BenchmarkTarget, output: str) -> Classification:
    if not (output or "").strip():
        return Classification("No", "BeRoot output empty")

    sections = parse_sections(output)
    file_perm = _section(sections, "Interesting files with write access")
    suid = _section(sections, "Suid Binaries")
    sudo_rules = _section(sections, "Sudo rules", "Sudoers file")
    sudo_capture = _section(sections, "sudo -l (runner capture)")
    sudo_text = "\n".join(x for x in (sudo_rules, sudo_capture, output) if x)
    caps = _section(sections, "Capabilities")
    nfs = _section(sections, "Root Squashing - /etc/exports")
    ldpreload = _section(sections, "LD_PRELOAD")
    py_hijack = _section(sections, "Writable Python Library Directory")
    creds = _section(sections, "Credential leaks")
    docker = _section(sections, "Docker", "Mounted docker socket")
    exploits = _section(sections, "Exploits")
    ptrace = _section(sections, "Ptrace Scope")
    sgid = _section(sections, "SGID binaries")
    doas = _section(sections, "Doas")
    network = _section(sections, "Network services")
    env_keep = _section(sections, "Sudo env_keep")
    shell = _section(sections, "Shell restrictions")
    system = _section(sections, "System configuration")
    mysql = _section(sections, "MySQL socket")
    path_dirs = _section(sections, "Writable PATH / hook directories")

    tid = target.id
    family = target.family
    prim = target.primitive or ""

    if family in (FAMILY_SUDO, FAMILY_SUDO_ADVANCED):
        return _classify_sudo(target, output, sections)

    if family == FAMILY_SUID:
        if _suid_lab_hit(target, suid):
            return Classification("Yes", _snippet(suid), "suid_bins")
        return Classification("No", "lab SUID binary not flagged")

    if family == FAMILY_CAPABILITIES:
        binary = prim
        if ":" in (target.misconfig or ""):
            binary = (target.misconfig or "").split(":", 1)[1]
        if _capability_hits(caps, binary):
            return Classification("Yes", _snippet(caps), "capabilities")
        return Classification("No", "no capabilities output")

    if family == FAMILY_WRITABLE:
        combined = "\n".join(x for x in (file_perm, path_dirs) if x)
        if (
            _writable_hits(file_perm, prim)
            or _writable_hits(path_dirs, prim)
            or _writable_target_hits(file_perm, target)
            or _writable_target_hits(path_dirs, target)
        ):
            return Classification("Yes", _snippet(combined or file_perm), "file_permissions")
        return Classification("No", "path not in scanned file_permissions list")

    if family == FAMILY_PYTHON:
        if tid == "python-hijack" and py_hijack.strip():
            return Classification("Yes", _snippet(py_hijack), "python_library_hijacking")
        needles = (
            "/opt/bench/phpinc",
            "/opt/bench/prepend.php",
            "/home/lowpriv/cwd_hijack",
            "phpinc",
            "prepend.php",
            "cwd_hijack",
        )
        combined = "\n".join(x for x in (path_dirs, file_perm) if x)
        if any(_writable_hits(combined, n) or n in combined for n in needles):
            return Classification("Yes", _snippet(combined), "writable_path_dirs")
        return Classification("No", "no PHP/Node/cwd include hijack path flagged")

    if family == FAMILY_NFS:
        if "no_root_squash" in nfs.lower():
            return Classification("Yes", _snippet(nfs), "nfs_root_squashing")
        if (
            _writable_hits(file_perm, prim)
            or _writable_hits(file_perm, "/etc/exports")
            or _writable_target_hits(file_perm, target)
        ):
            return Classification("Yes", _snippet(file_perm), "file_permissions")
        return Classification("No", "no NFS exports signal")

    if family == FAMILY_PATH:
        combined = "\n".join(x for x in (path_dirs, file_perm, network) if x)
        path_blob = (path_dirs + "\n" + file_perm).lower()
        path_hit = any(
            token in path_blob
            for token in (
                "pathhijack",
                "writable path entry",
                "nodeinc",
                "preload",
                "/opt/bench/",
            )
        )
        net_hit = bool(network.strip()) and (
            "localhost" in network.lower()
            or "listener" in network.lower()
            or "8877" in network
            or "9998" in network
        )
        if tid == "root-tcp-service" and net_hit:
            prefer = ("8877",) if "8877" in network else ("localhost tcp listener",)
            return Classification(
                "Yes",
                _snippet(combined, prefer=prefer),
                "network_services",
            )
        if path_hit:
            return Classification("Yes", _snippet(combined), "writable_path_dirs")
        return Classification("No", "no PATH poller / localhost service checks")

    if family == FAMILY_SGID:
        if "/opt/bench/" in sgid or "[non-standard]" in sgid.lower():
            return Classification("Yes", _snippet(sgid), "sgid_bins")
        return Classification("No", "no non-standard SGID signal")

    if family == FAMILY_DOAS:
        if "uid=0" in doas or "permit nopass" in doas.lower() or "permit " in doas.lower():
            return Classification("Yes", _snippet(doas), "doas_rules")
        return Classification("No", "no doas signal")

    if family == FAMILY_SHELL:
        if "restricted shell" in shell.lower() or "rbash" in shell.lower():
            return Classification("Yes", _snippet(shell), "shell_restrictions")
        return Classification("No", "no restricted-shell check")

    if family == FAMILY_CREDENTIALS and not tid.startswith("cred-"):
        if "without password" in mysql.lower() or "mysql socket:" in mysql.lower():
            return Classification("Yes", _snippet(mysql), "mysql_socket")
        return Classification("No", "no mysql socket signal")

    if family == FAMILY_SERVICES:
        sys_l = system.lower()
        service_rules = (
            ("apparmor-detect-only", "apparmor-status:", system, "system_info"),
            ("cgroup-detect-only", "cgroup-surface:", system, "system_info"),
            ("selinux-detect-only", "selinux-status:", system, "system_info"),
            ("fstab-detect-only", ("fstab-entry:", "fstab-status:", "fstab-surface:"), system, "system_info"),
            ("mounts-detect-only", "mount-option:", system, "system_info"),
            ("pkexec-detect-only", "pkexec-surface:", system, "system_info"),
            ("dbus-detect-only", "dbus-surface:", system, "system_info"),
            ("namespaces-detect-only", "userns-surface:", system, "system_info"),
            ("sudo-version-detect-only", "sudo-version:", system, "system_info"),
            ("docker-detect-only", "docker-surface:", system, "system_info / docker"),
        )
        for rule_id, marker, blob, check in service_rules:
            if tid != rule_id:
                continue
            blob_l = (blob or "").lower()
            markers = marker if isinstance(marker, tuple) else (marker,)
            if any(m in blob_l for m in markers):
                return Classification("Yes", _snippet(blob, prefer=markers), check)
        if tid == "docker-detect-only" and docker.strip():
            return Classification("Yes", _snippet(docker), "docker")
        if tid == "capabilities-detect-only" and (
            caps.strip() or "cap-hints:" in sys_l
        ):
            return Classification("Yes", _snippet(caps or system), "capabilities / system_info")
        if tid == "redis-unauth" and (
            "redis" in network.lower() or "unauthenticated" in network.lower()
        ):
            return Classification(
                "Yes",
                _snippet(network, prefer=("redis", "unauthenticated")),
                "network_services",
            )
        if tid == "root-tcp-service" and (
            "8877" in network or "localhost tcp listener" in network.lower()
        ):
            return Classification(
                "Yes",
                _snippet(network, prefer=("8877", "localhost tcp")),
                "network_services",
            )
        if tid == "root-udp-service" and (
            "9998" in network or "localhost udp listener" in network.lower()
        ):
            return Classification(
                "Yes",
                _snippet(network, prefer=("9998", "localhost udp")),
                "network_services",
            )
        if tid == "ptrace-detect-only" and ptrace.strip():
            return Classification("Yes", _snippet(ptrace), "ptrace_scope")
        if tid in {"exploits-detect-only", "kernel-detect-only"}:
            if exploits.strip() and _contains_any(
                exploits, ("kernel", "CVE-", "exploit", "Available information")
            ):
                return Classification("Yes", _snippet(exploits), "exploits")
            return Classification("No", "exploit suggester empty")

        detect_map = {
            "apparmor-detect-only": ("No", "no AppArmor check"),
            "cgroup-detect-only": ("No", "no cgroup check"),
            "dbus-detect-only": ("No", "no D-Bus policy check"),
            "fstab-detect-only": ("No", "no fstab/mount check"),
            "mounts-detect-only": ("No", "no mount enumeration"),
            "namespaces-detect-only": ("No", "no user-namespace abuse check"),
            "pkexec-detect-only": ("No", "no pkexec rule/version check"),
            "selinux-detect-only": ("No", "no SELinux check"),
            "sudo-version-detect-only": ("No", "no sudo -V/CVE check"),
            "docker-detect-only": ("No", "docker not detected"),
            "capabilities-detect-only": ("No", "no capabilities output"),
            "root-tcp-service": ("No", "no network service / socket enumeration"),
            "root-udp-service": ("No", "no network service / socket enumeration"),
            "redis-unauth": ("No", "no network service / socket enumeration"),
            "ptrace-detect-only": ("No", "no ptrace output"),
        }
        if tid in detect_map:
            verdict, reason = detect_map[tid]
            return Classification(verdict, reason)

    if creds.strip() and tid.startswith("cred-"):
        return Classification("Yes", _snippet(creds), "credential_leaks")

    return Classification("No", "no matching BeRoot check category")
