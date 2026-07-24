# -*- coding: utf-8 -*-
import os

from .files.file_manager import FileManager
from .files.files import File


class InterestingFiles(object):
    """
    Interesting files
    """
    def __init__(self):

        self.files = [
            # directories (shallow walk — see _get_permissions max_depth)
            '/etc/init.d',
            '/etc/cron.d',
            '/etc/cron.daily',
            '/etc/cron.hourly',
            '/etc/cron.monthly',
            '/etc/cron.weekly',
            '/etc/ld.so.conf.d',
            '/etc/logrotate.d',
            '/etc/profile.d',
            '/etc/update-motd.d',
            '/etc/rsyslog.d',
            '/etc/ssh/sshd_config.d',
            '/etc/pam.d',
            '/etc/nginx/conf.d',
            '/etc/apache2/conf-available',
            '/etc/supervisor/conf.d',
            '/etc/udev/rules.d',
            '/etc/systemd/system/bench.service.d',
            '/var/www/bench',
            '/opt/bench',
            '/opt/bench/wildcard',
            '/opt/pathhijack',
            '/opt/pathhijack-suid',
            '/usr/local/lib/benchhijack',
            '/dev/shm/bench',

            # files
            '/etc/sudoers',
            '/etc/passwd',
            '/etc/shadow',
            '/etc/exports',
            '/etc/at.allow',
            '/etc/at.deny',
            '/etc/crontab',
            '/etc/cron.allow',
            '/etc/cron.deny',
            '/etc/anacrontab',
            '/etc/apache2/apache2.conf',
            '/etc/environment',
            '/etc/hosts',
            '/etc/ld.so.preload',
            '/etc/ld.so.conf',
            '/etc/fstab',
            '/etc/rc.local',
            '/etc/logrotate.conf',
            '/root/.bashrc',
            '/root/.ssh/authorized_keys',
            '/opt/bench/sudoers.pending',
            '/opt/bench/logrotate-hook.sh',
            '/opt/bench/root.sh',
            '/opt/bench/job.sh',
            '/opt/bench/mv-hook.sh',
            '/etc/cron.d/bench-writable',
            '/etc/profile.d/bench-hook.sh',
            '/etc/init.d/benchsvc',
            '/etc/openvpn/client/up.sh',
            '/etc/apache2/conf-available/bench.conf',
            '/etc/nginx/conf.d/bench.conf',
            '/etc/systemd/system/bench.service.d/override.conf',
            '/etc/supervisor/conf.d/bench.conf',
            '/etc/udev/rules.d/99-bench.rules',
            '/etc/ssh/sshd_config.d/99-bench.conf',
            '/tmp/bench/hook.sh',
            '/dev/shm/bench/hook.sh',
            '/var/spool/cron/crontabs/root',
        ]
        self.dir_max_depth = 2
        #print('Getting permissions of sensitive files.')
        self.properties = self._get_permissions(self.files)

    def _get_permissions(self, paths):
        """
        paths contains a tab of string
        return a tab of FileManager object
        """
        properties = []
        max_depth = getattr(self, "dir_max_depth", 2)
        for path in paths:

            if os.path.isdir(path):
                base_depth = path.rstrip("/").count("/")
                for root, dirs, files in os.walk(path):
                    depth = root.rstrip("/").count("/") - base_depth
                    if depth >= max_depth:
                        dirs[:] = []
                    for file in files:
                        fullpath = os.path.join(root, file)
                        fm = FileManager(fullpath, check_inside=True)
                        properties.append(fm)

            elif os.path.isfile(path) or os.path.exists(path):
                fm = FileManager(path, check_inside=True)
                properties.append(fm)

        return properties

    def _write_access_on_subfiles(self, f_info, user):
        has_write_access = []
        for subfiles in f_info.subfiles:
            for subfile in subfiles.paths:
                dir_writable = ''

                # Should be an executable (check if dirname is writable)
                if subfile.is_not_ascii:
                    f = File(subfile.dirname)
                    if f.is_writable(user):
                        dir_writable = '\n\t\t- directory: %s [writable]' % subfile.dirname

                if subfile.is_writable(user) and not subfiles.line.startswith('#'):
                    has_write_access.append(
                        '[writable: %s] => %s%s' % (subfile.path, subfiles.line, dir_writable)
                    )
        return has_write_access

    def write_access_on_files(self, user):
        has_write_access = []
        for p in self.properties: 
            perm = ''
            values = {}
            dir_writable = False 

            if p.file.is_writable(user):
                perm = '[writable]'

            subfiles = []
            if p.file.is_readable(user):
                subfiles = self._write_access_on_subfiles(p, user)

            # Should be an executable (check if dirname is writable)
            if p.file.is_not_ascii:
                f = File(p.file.dirname)
                if f.is_writable(user):
                    dir_writable = True

            if subfiles or perm or dir_writable:
                values = {
                    'path': '%s %s' % (p.file.path, perm)
                }

                if subfiles: 
                    values['subfiles'] = subfiles

                if dir_writable:
                    if subfiles: 
                        values['directory'] = '%s [writable]' % p.file.dirname

            if values: 
                has_write_access.append(values)

        # Check if /usr/lib, /lib, and /usr/local/lib are writable without walking inside
        for directory in ['/usr/lib', '/lib', '/usr/local/lib']:
            f = File(directory)
            if f.is_writable(user):
                has_write_access.append({
                    'path': '%s [writable]' % directory
                })

        return has_write_access
