#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import re
import sys
import subprocess

from .files.files import File
from .useful.useful import run_cmd

# Common distro SUID binaries — useful, but not by themselves a lab/misconfig signal.
DEFAULT_SUID_BASENAMES = frozenset(
    {
        "su",
        "sudo",
        "sudo.ws",
        "passwd",
        "chsh",
        "chfn",
        "newgrp",
        "gpasswd",
        "mount",
        "umount",
        "ping",
        "ping6",
        "traceroute",
        "traceroute6",
        "pkexec",
        "dbus-daemon-launch-helper",
        "polkit-agent-helper-1",
        "unix_chkpwd",
        "at",
        "doas",
        "fusermount",
        "fusermount3",
        "ntfs-3g",
        "snap-confine",
        "chromium-sandbox",
        "firejail",
        "Xorg.wrap",
        "ssh-keysign",
        "ssh-agent",
        "chage",
        "expiry",
        "unix_update",
        "pam_timestamp_check",
    }
)

# Relative command names that are noise when pulled from strings(1).
_SYSTEM_CALL_NOISE = frozenset(
    {
        "system",
        "strings",
        "objdump",
        "true",
        "false",
        "test",
        "echo",
        "printf",
        "which",
        "type",
        "exec",
        "exit",
        "wait",
        "read",
        "cd",
        "pwd",
        "export",
        "unset",
        "shift",
        "source",
        "eval",
        "execve",
        "execl",
        "execlp",
        "execle",
        "execv",
        "execvp",
        "execvpe",
        "dlopen",
        "dlsym",
    }
)

_RELATIVE_CMD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{1,64}$")
_MAX_ANALYZE_BYTES = 2 * 1024 * 1024


class SuidBins:

    def __init__(self, gtfobins):
        self.gtfobins = gtfobins
        self.list = self._get_suid_bin()
        self.writable_root_bins = self._get_writable_root_bins()
        self.is_string_present = self._is_bin_present("strings")
        self.is_objdump_present = self._is_bin_present("objdump")

    def _get_suid_bin(self):
        """
        List all suid binaries.
        Using find is much faster than walking the filesystem in Python.
        """
        cmd = "find / -perm -u=s -type f 2>/dev/null"
        process = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        out, _err = process.communicate()
        suid = []

        for file in out.strip().decode().split("\n"):
            if not file:
                continue
            suid.append(File(file))

        return suid

    def _get_writable_root_bins(self):
        """
        Root-owned world-writable executables (SUID bit may have been cleared).
        Generic signal for writable privileged helpers under common prefixes.
        """
        cmd = (
            "find /opt /usr/local /home /tmp /var/tmp -type f -user root "
            "\\( -perm -0002 -o -perm -0020 \\) -executable 2>/dev/null"
        )
        process = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        out, _err = process.communicate()
        results = []
        for path in out.strip().decode().split("\n"):
            if not path:
                continue
            results.append(File(path))
        return results

    def _is_bin_present(self, binary):
        out, _err = run_cmd("which %s" % binary)
        return bool(out)

    def _is_default_suid(self, path):
        base = os.path.basename(path)
        if base in DEFAULT_SUID_BASENAMES:
            return True
        # Versioned interpreters still count as non-default when SUID.
        return False

    def _is_built_in_bin(self, path):
        """
        Check if a binary exists on standard PATH prefixes without an absolute path.
        """
        for prefix in ("/bin", "/usr/bin", "/sbin", "/usr/sbin"):
            if os.path.exists(os.path.join(prefix, path)):
                return True
        return False

    def _file_size(self, path):
        try:
            return os.path.getsize(path)
        except OSError:
            return 0

    def _check_for_system_call(self, binary):
        """
        Detect system() and relative command names (PATH hijack candidates).
        """
        cmd = 'objdump -T %s | grep " system"' % binary
        out, _ = run_cmd(cmd)
        results = []
        if not out:
            return results

        cmd = "strings %s" % binary
        out, _ = run_cmd(cmd)
        seen = set()
        for line in out.split(b"\n"):
            if not isinstance(line, str):
                line = line.decode(sys.getfilesystemencoding(), errors="replace")

            for string in line.split():
                if string.startswith("/"):
                    continue
                if string.startswith("__"):
                    continue
                if string in _SYSTEM_CALL_NOISE or not _RELATIVE_CMD_RE.match(string):
                    continue
                # Built-in tools or other relative names → PATH/system abuse surface.
                if self._is_built_in_bin(string) or string.lower() not in DEFAULT_SUID_BASENAMES:
                    key = "%s -> %s" % (line.strip(), string)
                    if key not in seen:
                        seen.add(key)
                        results.append(key)
        return results[:20]

    def _check_for_exec_call(self, binary, user):
        """
        Check exec* targets and flag writable path dependencies.
        """
        cmd = (
            'strings %s | grep -E "execve|execl|execlp|execle|execv|execvp|execvpe"'
            % binary
        )
        out, _ = run_cmd(cmd)
        results = []
        blacklist_path = ("/dev/", "/var/", "/tmp/")

        if not out:
            return results

        cmd = "strings %s" % binary
        out, _ = run_cmd(cmd)
        for line in out.decode(errors="replace").split("\n"):
            if line.startswith("/") and os.path.exists(line):
                if not line.startswith(blacklist_path):
                    f = File(line)
                    if f.is_writable(user):
                        results.append("%s [writable]" % line)
        return results

    def _check_for_dynamic_loads(self, binary, user):
        """
        Flag dlopen/dynamic loads of writable modules (generic .so hijack).
        """
        cmd = 'strings %s | grep -E "\\.so|dlopen|LD_PRELOAD"' % binary
        out, _ = run_cmd(cmd)
        if not out:
            return []

        results = []
        seen = set()
        for line in out.decode(errors="replace").split("\n"):
            for token in line.split():
                if not token.endswith(".so") and ".so." not in token:
                    continue
                if not token.startswith("/"):
                    key = "relative module: %s" % token
                    if key not in seen:
                        seen.add(key)
                        results.append(key)
                    continue
                if not os.path.exists(token):
                    continue
                f = File(token)
                if f.is_writable(user):
                    key = "%s [writable]" % token
                    if key not in seen:
                        seen.add(key)
                        results.append(key)
        return results[:20]

    def _analyze_binary(self, path, user):
        """Run strings/objdump analysis only on non-default / smaller binaries."""
        if self._is_default_suid(path):
            return {}, False
        if self._file_size(path) > _MAX_ANALYZE_BYTES:
            return {}, False
        if not (self.is_string_present and self.is_objdump_present):
            extras = {}
            if self.is_string_present:
                found = self._check_for_exec_call(path, user)
                if found:
                    extras["[+] exec calls found"] = found
                found = self._check_for_dynamic_loads(path, user)
                if found:
                    extras["[+] dynamic loads found"] = found
            return extras, bool(extras)

        extras = {}
        found = self._check_for_system_call(path)
        if found:
            extras["[+] system calls found"] = found
        if self.is_string_present:
            found = self._check_for_exec_call(path, user)
            if found:
                extras["[+] exec calls found"] = found
            found = self._check_for_dynamic_loads(path, user)
            if found:
                extras["[+] dynamic loads found"] = found
        return extras, bool(extras)

    def check_suid_bins(self, user):
        interesting = []
        defaults = []

        for suid in self.list:
            tags = []
            if suid.is_writable(user):
                tags.append("writable")
            non_default = not self._is_default_suid(suid.path)
            if non_default:
                tags.append("non-standard")

            tag_str = (" [%s]" % ", ".join(tags)) if tags else ""
            values = {"suid": "%s%s" % (suid.path, tag_str)}

            shell_escape = self.gtfobins.find_binary(suid.basename)
            if shell_escape:
                values["[+] gtfobins found"] = shell_escape.split("\n")

            extras, has_abuse = self._analyze_binary(suid.path, user)
            values.update(extras)

            # Prefer non-standard, writable, or abuse-annotated entries first.
            if non_default or bool(tags) or has_abuse:
                interesting.append(values)
            else:
                defaults.append(values)

        for wb in self.writable_root_bins:
            # Skip if already listed as SUID.
            if any(s.path == wb.path for s in self.list):
                continue
            values = {
                "suid": "%s [writable root-owned executable]" % wb.path,
            }
            shell_escape = self.gtfobins.find_binary(wb.basename)
            if shell_escape:
                values["[+] gtfobins found"] = shell_escape.split("\n")
            interesting.append(values)

        return interesting + defaults
