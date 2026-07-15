# RamiGPT benchmark lab base image.
# One image for all families; intentional misconfigs are applied at container
# start from MISCONFIG=… (see apply-misconfig.sh). Compose only changes env/ports.
FROM ubuntu:latest

ARG DEBIAN_FRONTEND=noninteractive

# SSH + tooling needed by RamiGPT/BeRoot and by several misconfig profiles.
# Keep package set shared so we do not rebuild per-target images.
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
        sudo \
        openssh-server \
        openssh-client \
        ca-certificates \
        python3 \
        libcap2-bin \
        findutils \
        cron \
        vim \
        gawk \
        curl \
        wget \
        less \
        nano \
        tar \
        coreutils \
        gcc \
        libc6-dev \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash lowpriv && \
    echo 'lowpriv:password' | chpasswd && \
    echo 'root:password' | chpasswd

RUN echo "FLAG{======RamiGPTi=====}" > /root/flag.txt && \
    chmod 600 /root/flag.txt

# Baseline sudoers: no NOPASSWD for lowpriv (profiles add /etc/sudoers.d/*).
RUN echo '# RamiGPT bench: misconfigs applied at runtime via MISCONFIG' > /etc/sudoers.d/README && \
    chmod 440 /etc/sudoers.d/README && \
    visudo -cf /etc/sudoers

RUN mkdir -p /var/run/sshd && \
    echo 'PermitRootLogin yes' >> /etc/ssh/sshd_config && \
    echo 'PasswordAuthentication yes' >> /etc/ssh/sshd_config && \
    echo 'PermitEmptyPasswords no' >> /etc/ssh/sshd_config && \
    echo 'AllowTcpForwarding yes' >> /etc/ssh/sshd_config && \
    echo 'UseDNS no' >> /etc/ssh/sshd_config && \
    ssh-keygen -A

WORKDIR /home/lowpriv

ENV SSH_PORT=22
ENV MISCONFIG=

COPY apply-misconfig.sh /apply-misconfig.sh
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /apply-misconfig.sh /entrypoint.sh

CMD ["/entrypoint.sh"]
