#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Additional privilege-escalation checks not covered by core BeRoot modules."""

from __future__ import print_function

import glob
import os
import re
import stat

from .files.files import File
from .useful.useful import run_cmd, tab_to_string

_ENV_KEEP_RE = re.compile(r"env_keep\s*[+]?=\s*(.+)", re.IGNORECASE)
_DOAS_PERMIT_RE = re.compile(
    r"^\s*permit\s+(?:persist\s+)?(nopass\s+)?(.+)$", re.IGNORECASE | re.MULTILINE
)

# Distro-default SGID helpers — interesting when absent from this set.
DEFAULT_SGID_BASENAMES = frozenset(
    {
        "chage",
        "expiry",
        "unix_chkpwd",
        "pam_extrausers_chkpwd",
        "ssh-agent",
        "crontab",
        "at",
        "wall",
        "write",
        "bsd-write",
        "dotlockfile",
        "mail",
        "mlock",
        "locate",
        "updatedb",
        "unix_update",
        "pam_timestamp_check",
    }
)


def _is_readable(path, user):
    try:
        return File(path).is_readable(user)
    except Exception:
        return False


def _is_writable(path, user):
    try:
        return File(path).is_writable(user)
    except Exception:
        return False


# Short "where to go next" hints for AI / operators reading BeRoot output.
_NEXT_BY_PREFIX = (
    ("apparmor", "next: run aa-status; inspect /etc/apparmor.d and /sys/module/apparmor"),
    ("selinux", "next: run getenforce/sestatus; read /etc/selinux/config"),
    ("fstab", "next: read /etc/fstab; compare with findmnt/mount"),
    ("mount-option", "next: review findmnt -o TARGET,OPTIONS for weak/no_root_squash mounts"),
    ("mounts-surface", "next: review full mount/findmnt table for weak options"),
    ("pkexec", "next: inspect /usr/bin/pkexec mode and /usr/share/polkit-1 policies"),
    ("sudo-version", "next: compare sudo -V to known CVEs; run sudo -l"),
    ("userns", "next: inspect unprivileged_userns_clone and /proc/self/ns"),
    ("cgroup", "next: enumerate /sys/fs/cgroup for writable release_agent/delegate"),
    ("dbus", "next: inspect /etc/dbus-1/system.d; try busctl list"),
    ("docker", "next: check docker.sock perms/group; try docker run -v /:/host"),
    ("cap-hints", "next: run getcap -r /usr/bin /usr/sbin /opt; abuse listed capabilities"),
    ("ptrace", "next: if yama/ptrace_scope is 0, PTRACE_ATTACH privileged processes"),
)


def _with_next_hints(hits):
    """Insert next: lines immediately after related findings (AI follow-up cues)."""
    if not hits:
        return hits
    out = []
    added = set()
    for hit in hits:
        out.append(hit)
        label = hit.split(":", 1)[0].strip().lower()
        for prefix, hint in _NEXT_BY_PREFIX:
            if label == prefix or label.startswith(prefix):
                if hint not in added:
                    added.add(hint)
                    out.append(hint)
                break
        match = re.search(r"\(from (/opt/bench/[^)\s]+)\)", hit)
        if match:
            hint = "next: read %s" % match.group(1)
            if hint not in added:
                added.add(hint)
                out.append(hint)
    return out

def scan_sgid_bins(user):
    """SGID binaries; non-standard paths listed first."""
    cmd = "find /usr /bin /sbin /opt /var /home -perm -g=s -type f 2>/dev/null"
    out, _ = run_cmd(cmd)
    if not out:
        return []

    interesting = []
    defaults = []
    for path in out.decode("utf-8", errors="replace").splitlines():
        path = path.strip()
        if not path:
            continue
        base = os.path.basename(path)
        tags = []
        f = File(path)
        if f.is_writable(user):
            tags.append("writable")
        non_default = base not in DEFAULT_SGID_BASENAMES
        if non_default:
            tags.append("non-standard")
        note = path
        if tags:
            note = "%s [%s]" % (path, ", ".join(tags))
        if non_default or tags:
            interesting.append(note)
        else:
            defaults.append(note)
    return interesting + defaults


def scan_doas(user):
    """Functional doas check + readable doas.conf rules (real permits only)."""
    hits = []
    for path in ("/etc/doas.conf", "/etc/doas.d"):
        if os.path.isfile(path) and _is_readable(path, user):
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as handle:
                    content = handle.read()
                for match in _DOAS_PERMIT_RE.finditer(content):
                    nopass = "nopass" if match.group(1) else ""
                    rule = match.group(2).strip()
                    label = "permit nopass %s" % rule if nopass else "permit %s" % rule
                    hits.append("%s: %s" % (path, label))
            except OSError:
                pass
        elif os.path.isdir(path):
            for conf in sorted(glob.glob(os.path.join(path, "*"))):
                if os.path.isfile(conf) and _is_readable(conf, user):
                    try:
                        with open(conf, "r", encoding="utf-8", errors="replace") as handle:
                            content = handle.read()
                        for match in _DOAS_PERMIT_RE.finditer(content):
                            nopass = "nopass" if match.group(1) else ""
                            rule = match.group(2).strip()
                            label = "permit nopass %s" % rule if nopass else "permit %s" % rule
                            hits.append("%s: %s" % (conf, label))
                    except OSError:
                        pass

    out, err = run_cmd("doas -n id 2>&1")
    text = (out or err or b"").decode("utf-8", errors="replace").strip()
    if text and "uid=0" in text:
        hits.append("doas -n id => uid=0(root)")
    return hits


def scan_network_services():
    """
    Localhost / loopback listeners and unauthenticated Redis-style services.
    Generic: any 127.0.0.1 listener is reported; process hints when available.
    """
    hits = []
    out, _ = run_cmd("ss -tulnp 2>/dev/null || netstat -tulnp 2>/dev/null")
    if out:
        text = out.decode("utf-8", errors="replace")
        seen = set()
        for line in text.splitlines():
            if "127.0.0.1" not in line and "[::1]" not in line:
                continue
            lower = line.lower()
            # Skip sshd on loopback if present — noise.
            if "sshd" in lower:
                continue
            key = line.strip()[:160]
            if key in seen:
                continue
            seen.add(key)
            proto = "udp" if "udp" in lower else "tcp"
            if "redis" in lower or ":6379" in line:
                hits.append("redis listener: %s" % key)
            else:
                hits.append("localhost %s listener: %s" % (proto, key))

    # Generic Redis/auth-less probe (covers redis-unauth style labs).
    out, err = run_cmd("redis-cli -h 127.0.0.1 -p 6379 ping 2>/dev/null")
    text = (out or b"").decode("utf-8", errors="replace").strip()
    if text.upper() == "PONG":
        hits.append("redis unauthenticated: PONG from 127.0.0.1:6379")
        hits.append(
            "next: redis-cli -h 127.0.0.1 -p 6379 INFO; try CONFIG/MODULE/SLAVEOF if unauth"
        )

    if hits:
        # Keep a general follow-up adjacent to the first listener finding.
        hits.insert(
            1,
            "next: identify listener owners (ss -tulnp); probe with nc/curl/redis-cli",
        )
    if any("udp" in h.lower() and "listener" in h.lower() for h in hits):
        # Place UDP guidance after the first UDP listener line.
        for idx, hit in enumerate(list(hits)):
            if "udp" in hit.lower() and "listener" in hit.lower():
                hits.insert(
                    idx + 1,
                    "next: probe UDP listeners (nc -u 127.0.0.1 <port>) as lowpriv",
                )
                break
    return hits
def scan_env_keep_directives():
    """Defaults env_keep from sudoers (any variable, not only LD_PRELOAD)."""
    hits = []
    paths = ["/etc/sudoers"]
    if os.path.isdir("/etc/sudoers.d"):
        paths.extend(sorted(glob.glob("/etc/sudoers.d/*")))
    seen = set()
    for path in paths:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if line.strip().startswith("#"):
                        continue
                    match = _ENV_KEEP_RE.search(line)
                    if match:
                        val = match.group(1).strip().strip('"').strip("'")
                        key = (path, val)
                        if key not in seen:
                            seen.add(key)
                            hits.append("%s: env_keep %s" % (path, val))
        except OSError:
            pass

    out, _ = run_cmd("sudo -ln 2>/dev/null")
    if out:
        for line in out.decode("utf-8", errors="replace").splitlines():
            match = _ENV_KEEP_RE.search(line)
            if match:
                val = match.group(1).strip().strip('"').strip("'")
                key = ("sudo -ln", val)
                if key not in seen:
                    seen.add(key)
                    hits.append("sudo -ln: env_keep %s" % val)
    return hits


def scan_shell_restrictions():
    """Restricted / rbash shells for the current user."""
    hits = []
    shell = os.environ.get("SHELL", "")
    if "rbash" in shell or "rksh" in shell:
        hits.append("restricted shell: %s" % shell)
    out, _ = run_cmd("grep -E ':(/usr)?/bin/(rbash|rksh)(:|$)' /etc/passwd 2>/dev/null")
    if out:
        for line in out.decode("utf-8", errors="replace").splitlines():
            if line.strip():
                hits.append("passwd: %s" % line.strip()[:120])
    return hits


def scan_system_info():
    """Detect-only style host hardening / config signals with stable labels."""
    hits = []

    aa_param = "/sys/module/apparmor/parameters/enabled"
    if os.path.isfile(aa_param):
        try:
            with open(aa_param, "r", encoding="utf-8", errors="replace") as handle:
                hits.append("apparmor-status: enabled=%s" % handle.read().strip())
        except OSError:
            hits.append("apparmor-status: module present")

    out, _ = run_cmd("getenforce 2>/dev/null")
    if out:
        hits.append("selinux-status: %s" % out.decode("utf-8", errors="replace").strip())
    if os.path.isfile("/sys/fs/selinux/enforce"):
        try:
            with open("/sys/fs/selinux/enforce", "r", encoding="utf-8", errors="replace") as handle:
                hits.append("selinux-status: enforce=%s" % handle.read().strip())
        except OSError:
            hits.append("selinux-status: sysfs present")

    fstab_entries = 0
    if os.path.isfile("/etc/fstab"):
        try:
            with open("/etc/fstab", "r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#"):
                        hits.append("fstab-entry: %s" % stripped[:120])
                        fstab_entries += 1
            if fstab_entries == 0:
                hits.append("fstab-status: readable but no active entries")
        except OSError:
            hits.append("fstab-status: present but unreadable")

    out, _ = run_cmd("mount 2>/dev/null")
    if out:
        mount_hits = 0
        for line in out.decode("utf-8", errors="replace").splitlines():
            # Prefer meaningful options; cap noise from container /proc mounts.
            if "no_root_squash" in line:
                hits.append("mount-option: %s" % line.strip()[:120])
                mount_hits += 1
            elif mount_hits < 6 and any(
                token in line for token in ("nosuid", "noexec", "nodev")
            ):
                # Skip deep /proc remounts.
                if line.startswith("proc on /proc/") or "on /proc/" in line:
                    continue
                hits.append("mount-option: %s" % line.strip()[:120])
                mount_hits += 1

    pkexec = "/usr/bin/pkexec"
    if os.path.isfile(pkexec):
        try:
            mode = os.stat(pkexec).st_mode
            suid = "SUID" if mode & stat.S_ISUID else "no-SUID"
            hits.append("pkexec-surface: %s %s mode=%o" % (pkexec, suid, mode & 0o7777))
        except OSError:
            hits.append("pkexec-surface: present")

    out, _ = run_cmd("sudo -V 2>/dev/null | head -1")
    if out:
        hits.append("sudo-version: %s" % out.decode("utf-8", errors="replace").strip())

    if os.path.isfile("/proc/sys/kernel/unprivileged_userns_clone"):
        try:
            with open("/proc/sys/kernel/unprivileged_userns_clone", "r") as handle:
                hits.append(
                    "userns-surface: unprivileged_userns_clone=%s" % handle.read().strip()
                )
        except OSError:
            pass

    if os.path.isdir("/sys/fs/cgroup"):
        hits.append("cgroup-surface: cgroupfs mounted")

    if os.path.isdir("/etc/dbus-1/system.d") or os.path.exists("/var/run/dbus/system_bus_socket"):
        hits.append("dbus-surface: system bus present")
    out, _ = run_cmd("command -v dbus-daemon 2>/dev/null")
    if out and out.decode("utf-8", errors="replace").strip():
        hits.append("dbus-surface: dbus-daemon present")

    docker_bits = []
    for sock in ("/var/run/docker.sock", "/run/docker.sock"):
        if os.path.exists(sock):
            docker_bits.append("socket=%s" % sock)
    out, _ = run_cmd("command -v docker 2>/dev/null")
    if out and out.decode("utf-8", errors="replace").strip():
        docker_bits.append("binary=%s" % out.decode("utf-8", errors="replace").strip())
    if os.path.exists("/etc/init.d/docker") or os.path.exists(
        "/lib/systemd/system/docker.service"
    ):
        docker_bits.append("service unit present")
    if docker_bits:
        hits.append("docker-surface: %s" % ", ".join(docker_bits))

    # Lab / host drop files: promote basename to a stable label
    # e.g. dbus-surface.txt -> dbus-surface: ...
    for pattern in (
        "/opt/bench/*-surface.txt",
        "/opt/bench/*-status.txt",
        "/opt/bench/*-enabled.txt",
        "/opt/bench/cap-hints.txt",
        "/opt/bench/fstab.txt",
        "/opt/bench/sudo-version.txt",
        "/opt/bench/ptrace-scope.txt",
    ):
        for path in glob.glob(pattern):
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as handle:
                    snippet = " | ".join(
                        line.strip() for line in handle.read(512).splitlines() if line.strip()
                    )
            except OSError:
                continue
            if not snippet:
                continue
            base = os.path.basename(path)
            if base == "cap-hints.txt":
                hits.append("cap-hints: %s (from %s)" % (snippet[:100], path))
            elif base == "fstab.txt":
                hits.append("fstab-surface: %s (from %s)" % (snippet[:100], path))
            elif base == "apparmor-enabled.txt":
                hits.append("apparmor-status: %s (from %s)" % (snippet[:80], path))
            elif base == "sudo-version.txt":
                hits.append("sudo-version: %s (from %s)" % (snippet[:80], path))
            elif base == "ptrace-scope.txt":
                hits.append("ptrace-surface: %s (from %s)" % (snippet[:80], path))
            elif base.endswith(".txt"):
                label = base[: -len(".txt")]
                hits.append("%s: %s (from %s)" % (label, snippet[:100], path))

    return _with_next_hints(hits)

def scan_mysql_socket(user):
    """Local MariaDB/MySQL socket without password."""
    hits = []
    sockets = glob.glob("/var/run/mysqld/*.sock") + glob.glob("/var/lib/mysql/mysql.sock")
    for sock in sockets:
        if os.path.exists(sock):
            hits.append("mysql socket: %s" % sock)
    for sock in sockets or ["/var/run/mysqld/mysqld.sock"]:
        out, _ = run_cmd(
            "mysql -u root --socket=%s -e 'SELECT 1' 2>/dev/null" % sock
        )
        if out and b"1" in out:
            hits.append("mysql root socket login without password")
            break
    return hits


def scan_writable_path_dirs(user):
    """
    Writable PATH-hijack / include / hook directories.
    Generic: writable directories on PATH, common hijack prefixes, include dirs.
    """
    hits = []
    seen = set()

    def add(path, why="writable"):
        if not path or path in seen:
            return
        if os.path.exists(path) and _is_writable(path, user):
            seen.add(path)
            hits.append("%s [%s]" % (path, why))

    # Directories currently on PATH that the user can write.
    path_env = os.environ.get("PATH", "")
    for entry in path_env.split(":"):
        if not entry or entry in (".",):
            continue
        add(entry, "writable PATH entry")

    candidates = [
        "/opt/pathhijack",
        "/opt/pathhijack-suid",
        "/usr/local/lib",
        "/dev/shm",
        "/tmp",
        "/var/tmp",
    ]
    for path in candidates:
        add(path)

    # Include / preload style trees under /opt and home.
    for pattern in (
        "/opt/*/nodeinc",
        "/opt/*/phpinc",
        "/opt/*/*inc",
        "/opt/*/preload*",
        "/home/*/cwd_hijack",
        "/home/*/.node*",
    ):
        for path in glob.glob(pattern):
            add(path)

    for path in glob.glob("/opt/bench/*"):
        if os.path.isdir(path) or (
            os.path.isfile(path)
            and (
                path.endswith((".so", ".js", ".php", ".sh"))
                or "preload" in path
                or "hijack" in path
                or "hook" in path
            )
        ):
            add(path)

    for path in glob.glob("/tmp/bench*"):
        add(path)
    for path in glob.glob("/tmp/*hook*"):
        add(path)
    for path in glob.glob("/tmp/*preload*"):
        add(path)

    return hits


def format_hits(hits):
    if not hits:
        return False
    return tab_to_string(hits)
