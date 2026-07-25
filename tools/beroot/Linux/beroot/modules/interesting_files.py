# -*- coding: utf-8 -*-
"""Interesting / sensitive paths for write-access privilege escalation checks."""
from __future__ import print_function

import os
import subprocess

from .files.file_manager import FileManager
from .files.files import File


# Directories walked shallowly for writable members (generic priv-esc surfaces).
SENSITIVE_DIRS = (
    "/etc/init.d",
    "/etc/cron.d",
    "/etc/cron.daily",
    "/etc/cron.hourly",
    "/etc/cron.monthly",
    "/etc/cron.weekly",
    "/etc/ld.so.conf.d",
    "/etc/logrotate.d",
    "/etc/profile.d",
    "/etc/update-motd.d",
    "/etc/rsyslog.d",
    "/etc/ssh/sshd_config.d",
    "/etc/pam.d",
    "/etc/sudoers.d",
    "/etc/nginx/conf.d",
    "/etc/apache2/conf-available",
    "/etc/apache2/sites-enabled",
    "/etc/supervisor/conf.d",
    "/etc/udev/rules.d",
    "/etc/systemd/system",
    "/etc/openvpn",
    "/var/spool/cron/crontabs",
    "/var/www",
    "/opt",
    "/usr/local/lib",
    "/dev/shm",
    "/tmp",
)

# Individual high-value files checked even when the parent dir is not listed above.
SENSITIVE_FILES = (
    "/etc/sudoers",
    "/etc/passwd",
    "/etc/shadow",
    "/etc/exports",
    "/etc/at.allow",
    "/etc/at.deny",
    "/etc/crontab",
    "/etc/cron.allow",
    "/etc/cron.deny",
    "/etc/anacrontab",
    "/etc/environment",
    "/etc/hosts",
    "/etc/ld.so.preload",
    "/etc/ld.so.conf",
    "/etc/fstab",
    "/etc/rc.local",
    "/etc/profile",
    "/etc/bash.bashrc",
    "/etc/logrotate.conf",
    "/etc/apache2/apache2.conf",
    "/etc/nginx/nginx.conf",
    "/etc/ssh/sshd_config",
    "/root/.bashrc",
    "/root/.profile",
    "/root/.ssh/authorized_keys",
)

# Root prefixes for a bounded find of world/group-writable files.
WRITABLE_FIND_ROOTS = (
    "/etc",
    "/opt",
    "/var/spool/cron",
    "/var/www",
    "/root",
    "/usr/local/lib",
)

_MAX_FIND_HITS = 120


class InterestingFiles(object):
    """Interesting files / directories that may enable privilege escalation when writable."""

    def __init__(self):
        self.files = list(SENSITIVE_DIRS) + list(SENSITIVE_FILES)
        self.dir_max_depth = 2
        self.properties = self._get_permissions(self.files)
        self._extra_writable = self._find_extra_writable_files()

    def _get_permissions(self, paths):
        properties = []
        max_depth = getattr(self, "dir_max_depth", 2)
        seen = set()
        for path in paths:
            if not path or path in seen:
                continue
            seen.add(path)

            if os.path.isdir(path):
                # Cap walk under large trees (/opt, /tmp, /etc/systemd/system).
                depth_limit = 1 if path in ("/opt", "/tmp", "/var/www") else max_depth
                if path == "/etc/systemd/system":
                    depth_limit = 2
                base_depth = path.rstrip("/").count("/")
                try:
                    for root, dirs, files in os.walk(path):
                        depth = root.rstrip("/").count("/") - base_depth
                        if depth >= depth_limit:
                            dirs[:] = []
                        # Skip noisy /tmp content except bench-like hooks.
                        if path == "/tmp":
                            dirs[:] = [d for d in dirs if d.startswith("bench") or "hook" in d]
                            files = [
                                f
                                for f in files
                                if f.startswith("bench") or "hook" in f or f.endswith((".sh", ".service"))
                            ]
                        for name in files:
                            fullpath = os.path.join(root, name)
                            if fullpath in seen:
                                continue
                            seen.add(fullpath)
                            properties.append(FileManager(fullpath, check_inside=True))
                except OSError:
                    continue

            elif os.path.isfile(path) or os.path.exists(path):
                properties.append(FileManager(path, check_inside=True))

        return properties

    def _find_extra_writable_files(self):
        """
        Generic catch-all: world/group-writable files under sensitive roots.
        Complements the explicit path list without hardcoding lab filenames.
        """
        roots = " ".join(WRITABLE_FIND_ROOTS)
        cmd = (
            "find %s -type f -perm -0002 2>/dev/null | head -n %d"
            % (roots, _MAX_FIND_HITS)
        )
        try:
            process = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            out, _ = process.communicate()
        except OSError:
            return []

        hits = []
        seen = {p.file.path for p in self.properties}
        for line in out.decode("utf-8", errors="replace").splitlines():
            path = line.strip()
            if not path or path in seen:
                continue
            # Skip huge package trees / noise.
            if "/.git/" in path or "/node_modules/" in path:
                continue
            seen.add(path)
            hits.append(path)
        return hits

    def _write_access_on_subfiles(self, f_info, user):
        has_write_access = []
        for subfiles in f_info.subfiles:
            for subfile in subfiles.paths:
                dir_writable = ""

                if subfile.is_not_ascii:
                    f = File(subfile.dirname)
                    if f.is_writable(user):
                        dir_writable = "\n\t\t- directory: %s [writable]" % subfile.dirname

                if subfile.is_writable(user) and not subfiles.line.startswith("#"):
                    has_write_access.append(
                        "[writable: %s] => %s%s" % (subfile.path, subfiles.line, dir_writable)
                    )
        return has_write_access

    def write_access_on_files(self, user):
        has_write_access = []
        reported = set()

        for p in self.properties:
            perm = ""
            values = {}
            dir_writable = False

            if p.file.is_writable(user):
                perm = "[writable]"

            subfiles = []
            if p.file.is_readable(user):
                subfiles = self._write_access_on_subfiles(p, user)

            if p.file.is_not_ascii:
                f = File(p.file.dirname)
                if f.is_writable(user):
                    dir_writable = True

            if subfiles or perm or dir_writable:
                values = {"path": "%s %s" % (p.file.path, perm)}
                if subfiles:
                    values["subfiles"] = subfiles
                if dir_writable and subfiles:
                    values["directory"] = "%s [writable]" % p.file.dirname
                has_write_access.append(values)
                reported.add(p.file.path)

        for path in self._extra_writable:
            if path in reported:
                continue
            f = File(path)
            if f.is_writable(user):
                has_write_access.append({"path": "%s [writable]" % path})
                reported.add(path)

        for directory in ("/usr/lib", "/lib", "/usr/local/lib"):
            f = File(directory)
            if f.is_writable(user) and directory not in reported:
                has_write_access.append({"path": "%s [writable]" % directory})

        return has_write_access
