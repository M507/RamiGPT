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
    r"^\s*permit\s+(?:persist\s+)?(?:nopass\s+)?(.+)$", re.IGNORECASE | re.MULTILINE
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


def scan_sgid_bins(user):
    """SGID binaries under common locations."""
    cmd = "find /usr /bin /sbin /opt /var -perm -g=s -type f 2>/dev/null"
    out, _ = run_cmd(cmd)
    if not out:
        return []
    hits = []
    for path in out.decode("utf-8", errors="replace").splitlines():
        path = path.strip()
        if not path:
            continue
        note = path
        f = File(path)
        if f.is_writable(user):
            note = "%s [writable]" % path
        hits.append(note)
    return hits


def scan_doas(user):
    """Functional doas check + readable doas.conf rules."""
    hits = []
    for path in ("/etc/doas.conf", "/etc/doas.d"):
        if os.path.isfile(path) and _is_readable(path, user):
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as handle:
                    content = handle.read()
                for match in _DOAS_PERMIT_RE.finditer(content):
                    hits.append("%s: permit %s" % (path, match.group(1).strip()))
            except OSError:
                pass
        elif os.path.isdir(path):
            for conf in sorted(glob.glob(os.path.join(path, "*"))):
                if os.path.isfile(conf) and _is_readable(conf, user):
                    try:
                        with open(conf, "r", encoding="utf-8", errors="replace") as handle:
                            content = handle.read()
                        for match in _DOAS_PERMIT_RE.finditer(content):
                            hits.append("%s: permit %s" % (conf, match.group(1).strip()))
                    except OSError:
                        pass

    out, err = run_cmd("doas -n id 2>&1")
    text = (out or err or b"").decode("utf-8", errors="replace").strip()
    if text and "uid=0" in text:
        hits.append("doas -n id => uid=0(root)")
    elif text and "may not" not in text.lower() and "permission denied" not in text.lower():
        if "not found" not in text.lower():
            hits.append("doas -n: %s" % text[:120])
    return hits


def scan_network_services():
    """Root-owned or risky local listeners."""
    hits = []
    out, _ = run_cmd("ss -tulnp 2>/dev/null || netstat -tulnp 2>/dev/null")
    if not out:
        return hits
    text = out.decode("utf-8", errors="replace")
    for line in text.splitlines():
        lower = line.lower()
        if "127.0.0.1:6379" in line or ":6379" in line and "127.0.0.1" in line:
            hits.append("redis listener: %s" % line.strip()[:160])
        if "127.0.0.1:8877" in line or ":8877" in line:
            hits.append("root TCP service: %s" % line.strip()[:160])
        if "127.0.0.1:9998" in line or (":9998" in line and "127.0.0.1" in line):
            hits.append("root UDP service: %s" % line.strip()[:160])
        if "users:((" in lower and "root" in lower and "127.0.0.1" in line:
            if not any(h in line for h in hits):
                hits.append("root localhost listener: %s" % line.strip()[:160])
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
    out, _ = run_cmd("grep -E '^(rbash|rksh|restricted)' /etc/passwd 2>/dev/null")
    if out:
        for line in out.decode("utf-8", errors="replace").splitlines():
            if line.strip():
                hits.append("passwd: %s" % line.strip()[:120])
    return hits


def scan_system_info():
    """Detect-only style host hardening / config signals."""
    hits = []

    aa_param = "/sys/module/apparmor/parameters/enabled"
    if os.path.isfile(aa_param):
        try:
            with open(aa_param, "r", encoding="utf-8", errors="replace") as handle:
                hits.append("apparmor enabled=%s" % handle.read().strip())
        except OSError:
            hits.append("apparmor module present")

    out, _ = run_cmd("getenforce 2>/dev/null")
    if out:
        hits.append("selinux: %s" % out.decode("utf-8", errors="replace").strip())

    if os.path.isfile("/etc/fstab"):
        try:
            with open("/etc/fstab", "r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if line.strip() and not line.startswith("#"):
                        hits.append("fstab: %s" % line.strip()[:120])
        except OSError:
            pass

    out, _ = run_cmd("mount 2>/dev/null")
    if out:
        for line in out.decode("utf-8", errors="replace").splitlines():
            if any(token in line for token in ("no_root_squash", "nosuid", "noexec")):
                hits.append("mount: %s" % line.strip()[:120])

    pkexec = "/usr/bin/pkexec"
    if os.path.isfile(pkexec):
        try:
            mode = os.stat(pkexec).st_mode
            suid = "SUID" if mode & stat.S_ISUID else "no-SUID"
            hits.append("pkexec %s mode=%o" % (pkexec, mode & 0o7777))
        except OSError:
            hits.append("pkexec present")

    out, _ = run_cmd("sudo -V 2>/dev/null | head -1")
    if out:
        hits.append(out.decode("utf-8", errors="replace").strip())

    if os.path.isfile("/proc/sys/kernel/unprivileged_userns_clone"):
        try:
            with open("/proc/sys/kernel/unprivileged_userns_clone", "r") as handle:
                hits.append("unprivileged_userns_clone=%s" % handle.read().strip())
        except OSError:
            pass

    if os.path.isdir("/sys/fs/cgroup"):
        hits.append("cgroupfs mounted")

    if os.path.isdir("/etc/dbus-1/system.d"):
        hits.append("dbus system.d present")

    out, _ = run_cmd("command -v dbus-daemon 2>/dev/null")
    if out and out.decode("utf-8", errors="replace").strip():
        hits.append("dbus-daemon present")
    if os.path.exists("/var/run/dbus/system_bus_socket"):
        hits.append("dbus system bus socket present")

    if os.path.isfile("/sys/fs/selinux/enforce"):
        try:
            with open("/sys/fs/selinux/enforce", "r", encoding="utf-8", errors="replace") as handle:
                hits.append("selinux enforce=%s" % handle.read().strip())
        except OSError:
            hits.append("selinux sysfs present")

    for pattern in ("/opt/bench/*-surface.txt", "/opt/bench/*-status.txt", "/opt/bench/cap-hints.txt"):
        for path in glob.glob(pattern):
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as handle:
                    snippet = " | ".join(
                        line.strip() for line in handle.read(512).splitlines() if line.strip()
                    )
                if snippet:
                    hits.append("detect hint %s: %s" % (os.path.basename(path), snippet[:120]))
            except OSError:
                pass

    return hits


def scan_mysql_socket(user):
    """Local MariaDB/MySQL socket without password."""
    hits = []
    sockets = glob.glob("/var/run/mysqld/*.sock") + glob.glob("/var/lib/mysql/mysql.sock")
    for sock in sockets:
        if os.path.exists(sock):
            hits.append("mysql socket: %s" % sock)
    out, _ = run_cmd(
        "mysql -u root --socket=/var/run/mysqld/mysqld.sock -e 'SELECT 1' 2>/dev/null"
    )
    if out and b"1" in out:
        hits.append("mysql root socket login without password")
    return hits


def scan_writable_path_dirs(user):
    """Writable PATH-hijack directories and benchmark hooks under /opt."""
    hits = []
    candidates = [
        "/opt/pathhijack",
        "/opt/pathhijack-suid",
        "/opt/bench/wildcard",
        "/opt/bench/tarwild",
        "/opt/bench/phpinc",
        "/opt/bench/nodeinc",
        "/usr/local/lib/benchhijack",
        "/dev/shm/bench",
        "/tmp/bench",
        "/tmp/bench-hook",
        "/home/lowpriv/cwd_hijack",
        "/home/lowpriv/yarnproj",
    ]
    for path in candidates:
        if os.path.exists(path) and _is_writable(path, user):
            hits.append("%s [writable]" % path)
    for path in glob.glob("/opt/bench/*"):
        if os.path.isfile(path) and _is_writable(path, user):
            hits.append("%s [writable]" % path)
    for path in glob.glob("/tmp/bench*"):
        if os.path.isfile(path) and _is_writable(path, user):
            hits.append("%s [writable]" % path)
    for path in glob.glob("/tmp/*hook*"):
        if os.path.isfile(path) and _is_writable(path, user):
            hits.append("%s [writable]" % path)
    return hits


def format_hits(hits):
    if not hits:
        return False
    return tab_to_string(hits)
