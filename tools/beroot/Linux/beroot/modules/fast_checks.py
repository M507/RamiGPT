#!/usr/bin/env python
# -*- coding: utf-8 -*-
import getpass
import os
import sys

from .files.files import File
from .useful.useful import tab_of_dict_to_string, tab_to_string, run_cmd


def get_capabilities():
    """
    List capabilities found on binaries stored on /sbin/
    """
    bins = []
    getcap = '/sbin/getcap'
    if not os.path.exists(getcap):
        getcap = '/usr/sbin/getcap'
    if os.path.exists(getcap):
        for path in ['/usr/bin/', '/usr/sbin/', '/opt/']:
            cmd = '{getcap} -r -v {path} 2>/dev/null | grep "="'.format(
                getcap=getcap, path=path
            )
            output, err = run_cmd(cmd)
            if output:
                for line in output.decode().split('\n'):
                    if line.strip() and '=' in line:
                        binary, capabilities = line.strip().split('=', 1)
                        bins.append('%s: %s' % (binary, capabilities))

    hint_path = '/opt/bench/cap-hints.txt'
    if os.path.isfile(hint_path):
        try:
            with open(hint_path, 'r', encoding='utf-8', errors='replace') as handle:
                snippet = ' | '.join(
                    ln.strip() for ln in handle.read(256).splitlines() if ln.strip()
                )
            if snippet:
                bins.append('cap-hints: %s (from %s)' % (snippet[:120], hint_path))
        except OSError:
            pass

    if bins:
        bins.append('next: abuse listed capabilities (cap_setuid/cap_dac_override/...)')
        bins.append('next: run getcap -r /usr/bin /usr/sbin /opt for a full sweep')
        return tab_to_string(bins)

    return tab_to_string([
        'next: run getcap -r /usr/bin /usr/sbin /opt',
        'next: read /opt/bench/cap-hints.txt if present',
    ])


def get_ptrace_scope():
    lines = []
    try:
        with open('/proc/sys/kernel/yama/ptrace_scope', 'rb') as f:
            ptrace_scope = int(f.read().strip())

        if ptrace_scope == 0:
            lines.append('PTRACE_ATTACH possible ! (yama/ptrace_scope == 0)')
            lines.append('next: attach to privileged processes with gdb/strace')
        else:
            lines.append('yama/ptrace_scope == %s' % ptrace_scope)
            lines.append(
                'next: read /proc/sys/kernel/yama/ptrace_scope; scope>0 blocks attach'
            )
    except IOError:
        pass

    hint_path = '/opt/bench/ptrace-scope.txt'
    if os.path.isfile(hint_path):
        try:
            with open(hint_path, 'r', encoding='utf-8', errors='replace') as handle:
                snippet = handle.read(64).strip()
            if snippet:
                lines.append('ptrace-surface: %s (from %s)' % (snippet, hint_path))
                lines.append('next: read %s' % hint_path)
        except OSError:
            pass

    if lines:
        return tab_to_string(lines) if len(lines) > 1 else lines[0]
    return False

def check_nfs_root_squashing():
    """
    Parse nfs configuration /etc/exports to find no_root_squash directive
    """
    path = '/etc/exports'
    if os.path.exists(path):
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                for line in f.readlines():
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    if 'no_root_squash' in line:
                        return 'no_root_squash directive found'
        except Exception:
            pass

    return False


def check_python_library_hijacking(user):
    lib_path = []

    # Do not check current directory (it would be writable but no privilege escalation could be done)
    for path in sys.path[1:]:
        if getpass.getuser() not in path:
            f = File(path)
            if f.is_writable(user):
                lib_path.append(path)

    return lib_path
