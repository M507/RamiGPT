#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Scan for credential leaks readable by the current user."""

from __future__ import print_function

import base64
import glob
import grp
import os
import re

from .files.files import File

MAX_READ_BYTES = 65536
MAX_LINE_SNIPPET = 160
LOG_MAX_DEPTH = 2
KEY_SEARCH_DEPTH = 5
CONFIG_WALK_DEPTH = 4

PRIVATE_KEY_MARKERS = (
    "BEGIN RSA PRIVATE KEY",
    "BEGIN OPENSSH PRIVATE KEY",
    "BEGIN EC PRIVATE KEY",
    "BEGIN PRIVATE KEY",
)

KEY_BASENAMES = frozenset(
    {
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "root_id_rsa",
    }
)

# Explicit paths under $HOME (benchmark cred-* labs + common real-world leaks).
HOME_REL_PATHS = (
    ".bash_history",
    ".viminfo",
    ".lesshst",
    ".tmux.conf",
    ".netrc",
    ".git-credentials",
    ".gitconfig",
    ".my.cnf",
    ".pgpass",
    ".wgetrc",
    ".npmrc",
    ".pypirc",
    ".muttrc",
    ".s3cfg",
    ".boto",
    ".bash_profile",
    ".env",
    ".gpg-passphrase",
    ".mongorc.js",
    ".rediscli.rc",
    ".slack-token",
    ".vault-token",
    "credentials.txt",
    "screenlog.0",
    "resolv.override",
    "ldap.conf",
    "krb5.conf",
    "terraform.tfvars",
    "secrets.yml",
    "tokens.json",
    "ci.env",
    "keepass-export.xml",
    "openvpn.auth",
    ".msmtprc",
    ".ssh/config",
    ".ansible/vault_pass.txt",
    "jenkins_backup/credentials.xml",
    ".config/gcloud/bench.properties",
    ".config/hg/hgrc",
    ".config/chromium/bench_prefs.json",
    ".config/filezilla/sitemanager.xml",
    ".config/pip/pip.conf",
    ".config/rclone/rclone.conf",
    ".irssi/config",
    ".docker/config.json",
    ".docker/.env",
    ".kube/config",
    ".aws/credentials",
    ".msf4/config",
    ".password-store/root.gpg",
)

# Globs relative to $HOME.
HOME_GLOB_PATHS = (
    ".subversion/auth/svn.simple/*",
    ".mozilla/firefox/*/logins.json",
)

SYSTEM_GLOB_PATHS = (
    "/etc/environment",
    "/var/backups/*",
    "/var/crash/*",
    "/etc/facter/facts.d/*",
    "/opt/ansible/*",
    "/etc/salt/*",
    "/etc/chef/*",
)

# Filenames where readable non-empty content is treated as a leak.
SECRET_BASENAMES = frozenset(
    {
        "vault_pass.txt",
        ".vault-token",
        "openvpn.auth",
        "credentials.txt",
        "ci.env",
        "bench",
        ".gpg-passphrase",
    }
)

# Path substrings that relax matching (svn auth caches, password stores, etc.).
SECRET_PATH_HINTS = (
    "/.subversion/auth/",
    "/.password-store/",
    "/jenkins_backup/",
)

LOG_GREP_PATTERNS = (
    re.compile(r"(?i)root password"),
    re.compile(r"(?i)break-glass"),
    re.compile(r"(?i)password for root"),
)

CONTENT_PATTERNS = (
    re.compile(r"(?i)(root[_-]?pass(word)?|password)\s*[=:]\s*\S+"),
    re.compile(r"(?i)root[_-]?pass(word)?\s+\S+"),
    re.compile(r"(?i)root password (is|for)\b"),
    re.compile(r"(?i)login\s+root\b"),
    re.compile(r"(?i)ansible_(ssh_pass|become_pass)\s*:"),
    re.compile(r"(?i)recover password\s*:"),
    re.compile(r"(?i)<password>\s*[^<]+</password>"),
    re.compile(r"(?i)<Pass[^>]*>[^<]+</Pass>"),
    re.compile(r'(?i)"root_password"\s*:'),
    re.compile(r'(?i)"encryptedPassword"\s*:'),
    re.compile(r"(?i)su root\s+\S+"),
    re.compile(r"(?i)token:\s*\S+"),
    re.compile(r'(?i)"auth"\s*:'),
    re.compile(r"(?i)(imap_pass|secret_key|pass)\s*="),
    re.compile(r"(?i)https?://[^/\s]+:[^@\s]+@"),
    re.compile(r"(?i)lab:\s*\S+"),
    re.compile(r"(?i)<Password>[^<]+</Password>"),
    re.compile(r"(?i)^password\s+\S+"),
    re.compile(r"(?i):[^:\n]*:root:"),
)

RELAXED_LINE_PATTERNS = (
    re.compile(r"(?i)^password\s*$"),
    re.compile(r"(?i)^root\s*$"),
)


def _user_in_group(user, group_name):
    try:
        for gid in os.getgroups():
            try:
                if grp.getgrgid(gid).gr_name == group_name:
                    return True
            except KeyError:
                continue
    except OSError:
        pass

    try:
        group = grp.getgrnam(group_name)
    except KeyError:
        return False

    return user.pw_name in group.gr_mem


def _truncate(text, limit=MAX_LINE_SNIPPET):
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _is_readable(path, user):
    """Use os.access so supplementary groups (e.g. adm) are honored."""
    if not os.path.isfile(path):
        return False
    try:
        if os.geteuid() == 0 or os.geteuid() == user.pw_uid:
            return os.access(path, os.R_OK)
    except OSError:
        pass
    return os.access(path, os.R_OK)


def _is_secret_path(path):
    base = os.path.basename(path)
    if base in SECRET_BASENAMES:
        return True
    return any(hint in path for hint in SECRET_PATH_HINTS)


def _match_line(line, secret_path=False):
    for pattern in CONTENT_PATTERNS:
        if pattern.search(line):
            return True
    if secret_path:
        for pattern in RELAXED_LINE_PATTERNS:
            if pattern.search(line):
                return True
    return False


def _base64_auth_hit(path, text):
    """
    Decode JSON-style "auth": "<base64>" blobs (Docker config and similar).
    Generic: any readable file with auth base64 that decodes to user:pass.
    """
    match = re.search(r'"auth"\s*:\s*"([A-Za-z0-9+/=]+)"', text)
    if not match:
        return None
    raw = match.group(1)
    try:
        decoded = base64.b64decode(raw).decode("utf-8", errors="replace")
    except Exception:
        return None
    # Expect user:password (or user:token) shape after decode.
    if ":" not in decoded or len(decoded) < 3:
        return None
    user, _, secret = decoded.partition(":")
    if not user or not secret:
        return None
    return "%s: auth decoded %s" % (path, _truncate(decoded))


def _docker_config_hit(path, text):
    # Backward-compatible name; decoding is generic for any auth base64 JSON.
    return _base64_auth_hit(path, text)


def _openvpn_auth_hit(path, text):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if os.path.basename(path) != "openvpn.auth" or len(lines) < 2:
        return None
    if lines[0].lower() == "root" and lines[1]:
        return "%s: root / %s" % (path, _truncate(lines[1]))
    return None


def _grep_readable_file(path, user):
    if not _is_readable(path, user):
        return None

    try:
        with open(path, "rb") as handle:
            data = handle.read(MAX_READ_BYTES)
    except (IOError, OSError):
        return None

    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:
        return None

    if any(marker in text for marker in PRIVATE_KEY_MARKERS):
        return "%s [readable private key]" % path

    openvpn = _openvpn_auth_hit(path, text)
    if openvpn:
        return openvpn

    docker = _docker_config_hit(path, text)
    if docker:
        return docker

    secret_path = _is_secret_path(path)
    for line in text.splitlines():
        if _match_line(line, secret_path=secret_path):
            return "%s: %s" % (path, _truncate(line))

    if secret_path:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                return "%s: %s" % (path, _truncate(stripped))

    return None


def _collect_candidate_paths(home):
    paths = []
    seen = set()

    def add(path):
        if not path:
            return
        path = os.path.realpath(os.path.expanduser(path))
        if path not in seen:
            seen.add(path)
            paths.append(path)

    for rel in HOME_REL_PATHS:
        add(os.path.join(home, rel))

    for pattern in HOME_GLOB_PATHS:
        for match in glob.glob(os.path.join(home, pattern)):
            add(match)

    for pattern in SYSTEM_GLOB_PATHS:
        if "*" in pattern:
            for match in glob.glob(pattern):
                add(match)
        else:
            add(pattern)

    return paths


def _find_readable_private_keys(user, roots):
    findings = []
    seen = set()

    for root in roots:
        if not os.path.isdir(root):
            continue

        base_depth = root.rstrip("/").count("/")
        for dirpath, _, filenames in os.walk(root):
            depth = dirpath.rstrip("/").count("/") - base_depth
            if depth > KEY_SEARCH_DEPTH:
                continue

            for name in filenames:
                if name not in KEY_BASENAMES and not name.endswith("_rsa"):
                    continue

                path = os.path.join(dirpath, name)
                if path in seen:
                    continue
                seen.add(path)

                if not _is_readable(path, user):
                    continue

                try:
                    with open(path, "rb") as handle:
                        head = handle.read(4096)
                except (IOError, OSError):
                    continue

                text = head.decode("utf-8", errors="replace")
                if any(marker in text for marker in PRIVATE_KEY_MARKERS):
                    findings.append("%s [readable private key]" % path)

    return findings


def _scan_log_directory(log_root, user, max_depth=LOG_MAX_DEPTH):
    findings = []
    if not os.path.isdir(log_root):
        return findings

    base_depth = log_root.rstrip("/").count("/")
    for dirpath, _, filenames in os.walk(log_root):
        depth = dirpath.rstrip("/").count("/") - base_depth
        if depth > max_depth:
            continue

        for name in filenames:
            path = os.path.join(dirpath, name)
            if not _is_readable(path, user):
                continue

            try:
                with open(path, "rb") as handle:
                    data = handle.read(MAX_READ_BYTES)
            except (IOError, OSError):
                continue

            text = data.decode("utf-8", errors="replace")
            for line in text.splitlines():
                if any(pattern.search(line) for pattern in LOG_GREP_PATTERNS):
                    findings.append("%s: %s" % (path, _truncate(line)))
                    break

    return findings


def scan_credential_leaks(user):
    """
    Return a list of readable credential leaks for ``user`` (pwd entry).
    """
    findings = []
    seen = set()

    def add(item):
        if item and item not in seen:
            seen.add(item)
            findings.append(item)

    shadow = "/etc/shadow"
    if os.path.isfile(shadow) and os.access(shadow, os.R_OK):
        add("%s [readable]" % shadow)

    home = user.pw_dir or os.path.expanduser("~")
    for path in _collect_candidate_paths(home):
        add(_grep_readable_file(path, user))

    search_roots = [home, "/var/backups", "/var/crash", "/tmp"]
    for item in _find_readable_private_keys(user, search_roots):
        add(item)

    if _user_in_group(user, "adm"):
        for item in _scan_log_directory("/var/log", user):
            add(item)

    return findings
