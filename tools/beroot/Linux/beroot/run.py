#!/usr/bin/env python
# -*- coding: utf-8 -*-

from .modules.exploit import Exploit
from .modules.docker import Docker
from .modules.users import Users
from .modules.services import Services
from .modules.suid import SuidBins
from .modules.interesting_files import InterestingFiles
from .modules.gtfobins import GTFOBins
from .modules.sudo.sudoers_file import SudoersFile
from .modules.sudo.sudo_list import SudoList
from .modules.useful.useful import tab_of_dict_to_string, tab_to_string
from .modules.sudoers import check_sudoers_misconfigurations
from .modules.fast_checks import (
    get_capabilities, get_ptrace_scope,
    check_nfs_root_squashing, check_python_library_hijacking,
)
from .modules.credentials import scan_credential_leaks
from .modules.extended_checks import (
    format_hits,
    scan_doas,
    scan_env_keep_directives,
    scan_mysql_socket,
    scan_network_services,
    scan_sgid_bins,
    scan_shell_restrictions,
    scan_system_info,
    scan_writable_path_dirs,
)


class RunChecks(object):

    def __init__(self, password):
        self.current_user = Users().current
        self.services = Services()
        self.file_info = InterestingFiles()
        self.gtfobins = GTFOBins()
        self.sudofile = SudoersFile()
        self.sudolist = SudoList(password)
        self.suids = SuidBins(self.gtfobins)

    # ------------------------ Files misconfigurations ------------------------

    def file_permissions(self):
        """
        Files too permissive
        """
        return (
            'Interesting files with write access',
            tab_of_dict_to_string(self.file_info.write_access_on_files(self.current_user))
        )

    def services_files_permissions(self):
        """
        Services with path too permissive
        """
        return (
            'Services ',
            tab_of_dict_to_string(self.services.write_access_on_binpath(self.current_user))
        )

    # ------------------------ Suid binaries ------------------------

    def suid_bins(self):
        """
        List Suid bins
        """
        return (
            'Suid Binaries ',
            tab_of_dict_to_string(self.suids.check_suid_bins(
                self.current_user),
                new_line=False, 
                title=False,
            )
        )

    # ------------------------ Sudo misconfigurations ------------------------

    def sudoers_misconfiguration(self):
        """
        Sudoers file (/etc/sudoers) 
        """
        rules = self.sudofile.rules_from_sudoers_file()
        return (
            'Sudoers file',
            check_sudoers_misconfigurations(self.file_info, self.services, self.suids, self.current_user, rules)
        )

    def sudo_list(self):
        """
        Sudo rules from sudo -ll output 
        """
        rules = self.sudolist.rules_from_sudo_ll()
        return (
            'Sudo rules',
            check_sudoers_misconfigurations(self.file_info, self.services, self.suids, self.current_user, rules)
        )

    def sudo_dirty_check(self):
        """
        Dirty check to be sure we not forgot a simple rules
        """
        return (
            'Sudo -i',
            self.sudolist.dirty_check(),
        )

    def ldpreload(self):
        """
        Check if LD_PRELOAD has been found in env_keep directive (sudoers rules)
        """
        return (
            'LD_PRELOAD',
            'Directive found' if self.sudofile.ld_preload or self.sudolist.ld_preload else False
        )

    # ------------------------ Docker misconfigurations ------------------------

    def docker_installed(self):
        """
        Check if docker is present
        """
        return (
            'Docker',
            Docker().is_docker_installed(),
        )

    def docker_mounted_sockets(self):
        """
        Check if docker is present
        """
        return (
            'Mounted docker socket',
            tab_of_dict_to_string(Docker().find_mounted_socket(self.current_user)),
        )

    # ------------------------ NFS Root Squashing ------------------------

    def nfs_root_squashing(self):
        """
        Check NFS Root Squashing - /etc/exports
        """
        return (
            'Root Squashing - /etc/exports',
            check_nfs_root_squashing(),
        )

    # ------------------------ Capabilities ------------------------

    def capabilities(self):
        """
        List capabilities from binaries located on /usr/bin/ and /usr/sbin/
        """
        return (
            'Capabilities',
            get_capabilities()
        )

    # ------------------------ Python Lib Hijacking ------------------------

    def python_library_hijacking(self):
        """
        Python Library Hijacking
        """
        return (
            'Writable Python Library Directory',
            tab_to_string(check_python_library_hijacking(self.current_user)),
        )

    # ------------------------ Ptrace ------------------------

    def ptrace_scope(self):
        """
        Check ptrace scope stored in /proc/sys/kernel/yama/ptrace_scope
        """
        return (
            'Ptrace Scope',
            get_ptrace_scope()
        )

    # ------------------------ Exploits ------------------------

    def exploits(self):
        """
        Run Linux exploit suggester
        """
        result = Exploit().run()
        if result:
            result = (
                "next: review Possible Exploits CVEs below; verify "
                "kernel/package versions before attempting\n"
                + result.lstrip()
            )
        return (
            'Exploits',
            result
        )

    # ------------------------ Credential leaks ------------------------

    def credential_leaks(self):
        """
        Readable secrets: configs, histories, SSH keys, shadow, adm logs.
        """
        return (
            'Credential leaks',
            tab_to_string(scan_credential_leaks(self.current_user)),
        )

    def sgid_bins(self):
        return (
            'SGID binaries',
            format_hits(scan_sgid_bins(self.current_user)),
        )

    def doas_rules(self):
        return (
            'Doas',
            format_hits(scan_doas(self.current_user)),
        )

    def network_services(self):
        return (
            'Network services',
            format_hits(scan_network_services()),
        )

    def env_keep_directives(self):
        return (
            'Sudo env_keep',
            format_hits(scan_env_keep_directives()),
        )

    def shell_restrictions(self):
        return (
            'Shell restrictions',
            format_hits(scan_shell_restrictions()),
        )

    def system_info(self):
        return (
            'System configuration',
            format_hits(scan_system_info()),
        )

    def mysql_socket(self):
        return (
            'MySQL socket',
            format_hits(scan_mysql_socket(self.current_user)),
        )

    def writable_path_dirs(self):
        return (
            'Writable PATH / hook directories',
            format_hits(scan_writable_path_dirs(self.current_user)),
        )


def print_output(output, to_print):
    category, result = output
    st = ''
    if result:
        st = '\n################ {category} ################\n\n{result}'.format(category=category, result=result)

        if to_print:
            print(st)

    return st


def run(password, to_print=True):
    """
    Can be useful when called from other tools - as a package
    beroot.py is not needed anymore
    This function returns all results found
    """

    total_found = ''

    checks = RunChecks(password)
    to_checks = [
        checks.file_permissions,
        checks.services_files_permissions,
        checks.suid_bins,
        checks.sudoers_misconfiguration,
        checks.sudo_list,
        checks.sudo_dirty_check,
        checks.docker_installed,
        checks.docker_mounted_sockets,
        checks.nfs_root_squashing,
        checks.ldpreload,
        checks.capabilities,
        checks.ptrace_scope,
        checks.exploits,
        checks.python_library_hijacking,
        checks.credential_leaks,
        checks.sgid_bins,
        checks.doas_rules,
        checks.network_services,
        checks.env_keep_directives,
        checks.shell_restrictions,
        checks.system_info,
        checks.mysql_socket,
        checks.writable_path_dirs,
    ]

    for c in to_checks:
        results = c()

        total_found += print_output(results, to_print=to_print)

    return total_found
