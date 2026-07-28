#!/usr/bin/env python
# -*- coding: utf-8 -*

import os

from .files.files import File

class Docker:
    """
    Docker misconfigurations
    """
    def __init__(self):

        self.sockets = [
            '/run/docker.sock',
            '/var/run/docker.sock'
        ]

    def is_docker_installed(self):
        """
        Check if docker is present (SysV init, systemd unit, binary, or socket).
        If present, could be used with gtfobins
            - https://gtfobins.github.io/gtfobins/docker/
        """
        present = (
            os.path.exists('/etc/init.d/docker')
            or os.path.exists('/lib/systemd/system/docker.service')
            or os.path.exists('/usr/lib/systemd/system/docker.service')
            or os.path.exists('/var/run/docker.sock')
            or os.path.exists('/run/docker.sock')
            or os.path.exists('/usr/bin/docker')
        )
        if present:
            return (
                "docker present (service/socket/binary)\n"
                "-> docker run -v /:/mnt --rm -it alpine chroot /mnt sh"
            )
        return False


    def find_mounted_socket(self, user):
        """
        List if a mounted docker socket has been found and if its path is writable
        """
        socks = []
        for socket in self.sockets:
            if os.path.exists(socket):
                socks.append({
                    'Sock': socket,
                    'Writable': "True" if File(socket).is_writable(user) else "False"
                })

        return socks
