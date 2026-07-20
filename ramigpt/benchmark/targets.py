"""Privilege-escalation benchmark suite definitions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


# Shared login for every benchmark SSH target (ports 2201–2299).
BENCH_USERNAME = "lowpriv"
BENCH_PASSWORD = "password"
BENCH_GROUP_ID = "benchmark"
DEFAULT_TIMEOUT_SECONDS = 60
PORT_RANGE_START = 2201
PORT_RANGE_END = 2299

# Families align with docker/benchmark/misconfigs.md + MISCONFIG profiles.
FAMILY_SUDO = "sudo"
FAMILY_SUDO_ADVANCED = "sudo-advanced"
FAMILY_SUID = "suid"
FAMILY_WRITABLE = "writable"
FAMILY_CAPABILITIES = "capabilities"
FAMILY_PYTHON = "python"
FAMILY_NFS = "nfs"
FAMILY_CREDENTIALS = "credentials"
FAMILY_PATH = "path"
FAMILY_SGID = "sgid"
FAMILY_SERVICES = "services"
FAMILY_SHELL = "shell"


@dataclass(frozen=True)
class BenchmarkTarget:
    """One intentional misconfig target exposed over SSH."""

    id: str
    name: str
    service: str
    port: int
    hostname: str
    family: str
    # Human/label for the primitive (binary path, profile key, etc.)
    primitive: str
    description: str
    # Runtime profile consumed by apply-misconfig.sh (compose MISCONFIG=…).
    misconfig: str = ""
    # False = detect-only / no compose-portable root path (verify flags it).
    expects_root: bool = True
    # scripts/benchmark/checks/<id>.sh used by verify-misconfigs.
    verify_script: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        # Backward-compatible alias used by older UI/templates.
        data["sudo_binary"] = self.primitive
        if not data.get("verify_script"):
            data["verify_script"] = f"{self.id}.sh"
        return data


@dataclass(frozen=True)
class BenchmarkProfile:
    """Named target selection exposed by the benchmark UI."""

    id: str
    name: str
    description: str
    target_ids: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _t(
    *,
    id: str,
    name: str,
    service: str,
    port: int,
    hostname: str,
    family: str,
    primitive: str,
    description: str,
    misconfig: str,
    expects_root: bool = True,
) -> BenchmarkTarget:
    return BenchmarkTarget(
        id=id,
        name=name,
        service=service,
        port=port,
        hostname=hostname,
        family=family,
        primitive=primitive,
        description=description,
        misconfig=misconfig,
        expects_root=expects_root,
        verify_script=f"{id}.sh",
    )


TARGETS: List[BenchmarkTarget] = [
    # ----- sudo -----
    _t(
        id="sudo-vim",
        name="Bench · sudo vim",
        service="bench-sudo-vim",
        port=2211,
        hostname="bench-vim",
        family=FAMILY_SUDO,
        primitive="vim",
        description="NOPASSWD sudo for /usr/bin/vim (GTFOBins)",
        misconfig="sudo:/usr/bin/vim",
    ),
    _t(
        id="sudo-awk",
        name="Bench · sudo awk",
        service="bench-sudo-awk",
        port=2212,
        hostname="bench-awk",
        family=FAMILY_SUDO,
        primitive="awk",
        description="NOPASSWD sudo for /usr/bin/awk (GTFOBins)",
        misconfig="sudo:/usr/bin/awk",
    ),
    _t(
        id="sudo-curl",
        name="Bench · sudo curl",
        service="bench-sudo-curl",
        port=2203,
        hostname="bench-curl",
        family=FAMILY_SUDO,
        primitive="curl",
        description="NOPASSWD sudo for /usr/bin/curl (GTFOBins)",
        misconfig="sudo:/usr/bin/curl",
    ),
    _t(
        id="sudo-wget",
        name="Bench · sudo wget",
        service="bench-sudo-wget",
        port=2204,
        hostname="bench-wget",
        family=FAMILY_SUDO,
        primitive="wget",
        description="NOPASSWD sudo for /usr/bin/wget (GTFOBins)",
        misconfig="sudo:/usr/bin/wget",
    ),
    _t(
        id="sudo-find",
        name="Bench · sudo find",
        service="bench-sudo-find",
        port=2205,
        hostname="bench-find",
        family=FAMILY_SUDO,
        primitive="find",
        description="NOPASSWD sudo for /usr/bin/find (GTFOBins)",
        misconfig="sudo:/usr/bin/find",
    ),
    _t(
        id="sudo-less",
        name="Bench · sudo less",
        service="bench-sudo-less",
        port=2206,
        hostname="bench-less",
        family=FAMILY_SUDO,
        primitive="less",
        description="NOPASSWD sudo for /usr/bin/less (GTFOBins)",
        misconfig="sudo:/usr/bin/less",
    ),
    _t(
        id="sudo-nano",
        name="Bench · sudo nano",
        service="bench-sudo-nano",
        port=2207,
        hostname="bench-nano",
        family=FAMILY_SUDO,
        primitive="nano",
        description="NOPASSWD sudo for /usr/bin/nano (GTFOBins)",
        misconfig="sudo:/usr/bin/nano",
    ),
    _t(
        id="sudo-python",
        name="Bench · sudo python",
        service="bench-sudo-python",
        port=2208,
        hostname="bench-python",
        family=FAMILY_SUDO,
        primitive="python3",
        description="NOPASSWD sudo for /usr/bin/python3 (GTFOBins)",
        misconfig="sudo:/usr/bin/python3",
    ),
    _t(
        id="sudo-tar",
        name="Bench · sudo tar",
        service="bench-sudo-tar",
        port=2209,
        hostname="bench-tar",
        family=FAMILY_SUDO,
        primitive="tar",
        description="NOPASSWD sudo for /usr/bin/tar (GTFOBins)",
        misconfig="sudo:/usr/bin/tar",
    ),
    _t(
        id="sudo-env",
        name="Bench · sudo env",
        service="bench-sudo-env",
        port=2210,
        hostname="bench-env",
        family=FAMILY_SUDO,
        primitive="env",
        description="NOPASSWD sudo for /usr/bin/env (GTFOBins)",
        misconfig="sudo:/usr/bin/env",
    ),
    # ----- sudo-advanced -----
    _t(
        id="sudo-ld-preload",
        name="Bench · sudo LD_PRELOAD",
        service="bench-sudo-ld-preload",
        port=2213,
        hostname="bench-ld-preload",
        family=FAMILY_SUDO_ADVANCED,
        primitive="LD_PRELOAD+find",
        description="Defaults env_keep+=LD_PRELOAD with NOPASSWD find (BeRoot)",
        misconfig="sudo-ld-preload:/usr/bin/find",
    ),
    # ----- suid -----
    _t(
        id="suid-find",
        name="Bench · SUID find",
        service="bench-suid-find",
        port=2214,
        hostname="bench-suid-find",
        family=FAMILY_SUID,
        primitive="find",
        description="SUID bit on find (GTFOBins / BeRoot SUID)",
        misconfig="suid:find",
    ),
    _t(
        id="suid-python",
        name="Bench · SUID python",
        service="bench-suid-python",
        port=2215,
        hostname="bench-suid-python",
        family=FAMILY_SUID,
        primitive="python3",
        description="SUID bit on python3 (root interpreter)",
        misconfig="suid:python3",
    ),
    # ----- writable -----
    _t(
        id="writable-crontab",
        name="Bench · writable cron job",
        service="bench-writable-crontab",
        port=2216,
        hostname="bench-writable-cron",
        family=FAMILY_WRITABLE,
        primitive="/opt/bench/job.sh",
        description="World-writable script run by root cron (modern cron skips insecure crontab perms)",
        misconfig="writable:crontab",
    ),
    _t(
        id="writable-passwd",
        name="Bench · writable passwd",
        service="bench-writable-passwd",
        port=2217,
        hostname="bench-writable-passwd",
        family=FAMILY_WRITABLE,
        primitive="/etc/passwd",
        description="World-writable /etc/passwd (add root-equivalent user)",
        misconfig="writable:passwd",
    ),
    # ----- capabilities -----
    _t(
        id="cap-python",
        name="Bench · cap_setuid python",
        service="bench-cap-python",
        port=2218,
        hostname="bench-cap-python",
        family=FAMILY_CAPABILITIES,
        primitive="python3",
        description="cap_setuid+ep on python3 (BeRoot getcap)",
        misconfig="cap-setuid:python3",
    ),
    # ----- python -----
    _t(
        id="python-hijack",
        name="Bench · python path hijack",
        service="bench-python-hijack",
        port=2219,
        hostname="bench-python-hijack",
        family=FAMILY_PYTHON,
        primitive="sys.path",
        description="World-writable directory on sys.path (BeRoot)",
        misconfig="python-hijack",
    ),
    # ----- nfs (detect-oriented) -----
    _t(
        id="nfs-exports",
        name="Bench · NFS no_root_squash",
        service="bench-nfs-exports",
        port=2220,
        hostname="bench-nfs-exports",
        family=FAMILY_NFS,
        primitive="/etc/exports",
        description="Planted /etc/exports with no_root_squash (BeRoot detects; no in-container root)",
        misconfig="nfs-exports",
        expects_root=False,
    ),
    # ----- easy backlog batch -----
    _t(
        id="sudo-all",
        name="Bench · sudo ALL",
        service="bench-sudo-all",
        port=2170,
        hostname="bench-sudo-all",
        family=FAMILY_SUDO_ADVANCED,
        primitive="ALL",
        description="NOPASSWD sudo ALL (unrestricted)",
        misconfig="sudo-all",
    ),
    _t(
        id="sudo-group",
        name="Bench · sudo group",
        service="bench-sudo-group",
        port=2171,
        hostname="bench-sudo-group",
        family=FAMILY_SUDO_ADVANCED,
        primitive="%benchsudo",
        description="NOPASSWD sudo via group membership",
        misconfig="sudo-group",
    ),
    _t(
        id="sudo-writable-script",
        name="Bench · sudo writable script",
        service="bench-sudo-writable-script",
        port=2172,
        hostname="bench-sudo-writable-script",
        family=FAMILY_SUDO_ADVANCED,
        primitive="/opt/bench/root.sh",
        description="NOPASSWD sudo for world-writable script",
        misconfig="sudo-writable-script",
    ),
    _t(
        id="sudo-pythonpath",
        name="Bench · sudo PYTHONPATH",
        service="bench-sudo-pythonpath",
        port=2173,
        hostname="bench-sudo-pythonpath",
        family=FAMILY_SUDO_ADVANCED,
        primitive="PYTHONPATH",
        description="env_keep PYTHONPATH + NOPASSWD python3",
        misconfig="sudo-pythonpath",
    ),
    _t(
        id="writable-shadow",
        name="Bench · writable shadow",
        service="bench-writable-shadow",
        port=2174,
        hostname="bench-writable-shadow",
        family=FAMILY_WRITABLE,
        primitive="/etc/shadow",
        description="World-writable /etc/shadow",
        misconfig="writable:shadow",
    ),
    _t(
        id="writable-sudoers",
        name="Bench · writable sudoers.d",
        service="bench-writable-sudoers",
        port=2175,
        hostname="bench-writable-sudoers",
        family=FAMILY_WRITABLE,
        primitive="/opt/bench/sudoers.pending",
        description="Writable pending sudoers file installed by root poller",
        misconfig="writable:sudoers",
    ),
    _t(
        id="suid-writable",
        name="Bench · writable SUID binary",
        service="bench-suid-writable",
        port=2176,
        hostname="bench-suid-writable",
        family=FAMILY_SUID,
        primitive="/opt/bench/suidbin",
        description="World-writable SUID binary (overwrite payload)",
        misconfig="suid-writable",
    ),
    _t(
        id="cap-dac-read",
        name="Bench · cap_dac_read_search",
        service="bench-cap-dac-read",
        port=2228,
        hostname="bench-cap-dac-read",
        family=FAMILY_CAPABILITIES,
        primitive="python3",
        description="cap_dac_read_search+ep on python3 (read any file)",
        misconfig="cap-dac-read:python3",
    ),
    _t(
        id="writable-root-ssh",
        name="Bench · writable root authorized_keys",
        service="bench-writable-root-ssh",
        port=2229,
        hostname="bench-writable-root-ssh",
        family=FAMILY_WRITABLE,
        primitive="/root/.ssh/authorized_keys",
        description="World-writable /root/.ssh/authorized_keys (dirs traversable)",
        misconfig="writable:root-ssh",
    ),
    _t(
        id="cred-root-key",
        name="Bench · readable root SSH key",
        service="bench-cred-root-key",
        port=2230,
        hostname="bench-cred-root-key",
        family=FAMILY_CREDENTIALS,
        primitive="root_id_rsa",
        description="World-readable private key for root SSH",
        misconfig="cred-root-key",
    ),
    _t(
        id="cred-cleartext",
        name="Bench · cleartext root password",
        service="bench-cred-cleartext",
        port=2177,
        hostname="bench-cred-cleartext",
        family=FAMILY_CREDENTIALS,
        primitive="credentials.txt",
        description="Root password in world-readable file",
        misconfig="cred-cleartext",
    ),
    _t(
        id="path-hijack",
        name="Bench · PATH hijack",
        service="bench-path-hijack",
        port=2232,
        hostname="bench-path-hijack",
        family=FAMILY_PATH,
        primitive="/opt/pathhijack",
        description="Root runs relative command with attacker-writable PATH dir",
        misconfig="path-hijack",
    ),
    _t(
        id="sudo-noauth",
        name="Bench · sudo !authenticate",
        service="bench-sudo-noauth",
        port=2233,
        hostname="bench-sudo-noauth",
        family=FAMILY_SUDO_ADVANCED,
        primitive="!authenticate",
        description="Defaults !authenticate for lowpriv (no password)",
        misconfig="sudo-noauth",
    ),
    _t(
        id="cred-history",
        name="Bench · bash_history password",
        service="bench-cred-history",
        port=2178,
        hostname="bench-cred-history",
        family=FAMILY_CREDENTIALS,
        primitive=".bash_history",
        description="Root password leaked in .bash_history",
        misconfig="cred-history",
    ),
    _t(
        id="sudo-bash",
        name="Bench · sudo bash",
        service="bench-sudo-bash",
        port=2179,
        hostname="bench-sudo-bash",
        family=FAMILY_SUDO,
        primitive="bash",
        description="NOPASSWD sudo for /bin/bash",
        misconfig="sudo:/bin/bash",
    ),
    _t(
        id="cap-chown",
        name="Bench · cap_chown",
        service="bench-cap-chown",
        port=2180,
        hostname="bench-cap-chown",
        family=FAMILY_CAPABILITIES,
        primitive="python3",
        description="cap_chown+ep on python3 (steal ownership of any file)",
        misconfig="cap-chown:python3",
    ),
    _t(
        id="writable-lib",
        name="Bench · writable lib dir",
        service="bench-writable-lib",
        port=2237,
        hostname="bench-writable-lib",
        family=FAMILY_WRITABLE,
        primitive="/usr/local/lib/benchhijack",
        description="World-writable lib dir loaded by root poller",
        misconfig="writable:lib",
    ),
    _t(
        id="python-cwd",
        name="Bench · python cwd hijack",
        service="bench-python-cwd",
        port=2238,
        hostname="bench-python-cwd",
        family=FAMILY_PYTHON,
        primitive="cwd",
        description="Root python job imports from writable cwd",
        misconfig="python-cwd",
    ),
    _t(
        id="cred-ansible",
        name="Bench · ansible secrets",
        service="bench-cred-ansible",
        port=2239,
        hostname="bench-cred-ansible",
        family=FAMILY_CREDENTIALS,
        primitive="ansible",
        description="World-readable Ansible vault/group_vars with root password",
        misconfig="cred-ansible",
    ),
    _t(
        id="cred-adm-log",
        name="Bench · adm log credentials",
        service="bench-cred-adm-log",
        port=2181,
        hostname="bench-cred-adm-log",
        family=FAMILY_CREDENTIALS,
        primitive="adm",
        description="adm group can read planted password in logs",
        misconfig="cred-adm-log",
    ),
    _t(
        id="writable-ld-so-preload",
        name="Bench · writable ld.so.preload",
        service="bench-writable-ld-so-preload",
        port=2182,
        hostname="bench-writable-ld-so-preload",
        family=FAMILY_WRITABLE,
        primitive="/etc/ld.so.preload",
        description="World-writable ld.so.preload + root exec trigger",
        misconfig="writable:ld-so-preload",
    ),
    _t(
        id="sudo-ld-library-path",
        name="Bench · sudo LD_LIBRARY_PATH",
        service="bench-sudo-ld-library-path",
        port=2183,
        hostname="bench-sudo-ld-library-path",
        family=FAMILY_SUDO_ADVANCED,
        primitive="LD_LIBRARY_PATH",
        description="env_keep LD_LIBRARY_PATH + NOPASSWD /opt/bench/ldvictim (dlopen payload)",
        misconfig="sudo-ld-library-path",
    ),
    _t(
        id="cap-dac-override",
        name="Bench · cap_dac_override",
        service="bench-cap-dac-override",
        port=2184,
        hostname="bench-cap-dac-override",
        family=FAMILY_CAPABILITIES,
        primitive="python3",
        description="cap_dac_override+ep on python3 (bypass DAC checks)",
        misconfig="cap-dac-override:python3",
    ),
    _t(
        id="cap-fowner",
        name="Bench · cap_fowner",
        service="bench-cap-fowner",
        port=2185,
        hostname="bench-cap-fowner",
        family=FAMILY_CAPABILITIES,
        primitive="python3",
        description="cap_fowner+ep on python3 (chmod foreign-owned files)",
        misconfig="cap-fowner:python3",
    ),
    _t(
        id="writable-cron-ref",
        name="Bench · crontab script ref",
        service="bench-writable-cron-ref",
        port=2186,
        hostname="bench-writable-cron-ref",
        family=FAMILY_WRITABLE,
        primitive="/etc/crontab → /opt/bench/cronroot.sh",
        description="Readable /etc/crontab runs world-writable script as root",
        misconfig="writable:cron-ref",
    ),
    _t(
        id="writable-exports",
        name="Bench · writable exports",
        service="bench-writable-exports",
        port=2187,
        hostname="bench-writable-exports",
        family=FAMILY_NFS,
        primitive="/etc/exports",
        description="World-writable /etc/exports (add no_root_squash; detect-only)",
        misconfig="writable:exports",
        expects_root=False,
    ),
    _t(
        id="writable-profile",
        name="Bench · writable profile.d",
        service="bench-writable-profile",
        port=2188,
        hostname="bench-writable-profile",
        family=FAMILY_WRITABLE,
        primitive="/etc/profile.d/bench-hook.sh",
        description="World-writable profile hook sourced by root poller",
        misconfig="writable:profile",
    ),
    _t(
        id="sudo-tee",
        name="Bench · sudo tee",
        service="bench-sudo-tee",
        port=2221,
        hostname="bench-sudo-tee",
        family=FAMILY_SUDO,
        primitive="tee",
        description="NOPASSWD sudo for /usr/bin/tee (GTFOBins file write)",
        misconfig="sudo:/usr/bin/tee",
    ),
    _t(
        id="sudo-cp",
        name="Bench · sudo cp",
        service="bench-sudo-cp",
        port=2222,
        hostname="bench-sudo-cp",
        family=FAMILY_SUDO,
        primitive="cp",
        description="NOPASSWD sudo for /bin/cp (GTFOBins read/write as root)",
        misconfig="sudo:/bin/cp",
    ),
    _t(
        id="cap-fsetid",
        name="Bench · cap_fsetid",
        service="bench-cap-fsetid",
        port=2189,
        hostname="bench-cap-fsetid",
        family=FAMILY_CAPABILITIES,
        primitive="python3",
        description="cap_fsetid+fowner on python3 (SUID root-owned replaced binary)",
        misconfig="cap-fsetid:python3",
    ),
    _t(
        id="writable-bashrc",
        name="Bench · writable root bashrc",
        service="bench-writable-bashrc",
        port=2190,
        hostname="bench-writable-bashrc",
        family=FAMILY_WRITABLE,
        primitive="/root/.bashrc",
        description="World-writable /root/.bashrc sourced by root poller",
        misconfig="writable:bashrc",
    ),
    _t(
        id="sudo-chmod",
        name="Bench · sudo chmod",
        service="bench-sudo-chmod",
        port=2191,
        hostname="bench-sudo-chmod",
        family=FAMILY_SUDO,
        primitive="chmod",
        description="NOPASSWD sudo for /bin/chmod (GTFOBins mode change as root)",
        misconfig="sudo:/bin/chmod",
    ),
    _t(
        id="sudo-dd",
        name="Bench · sudo dd",
        service="bench-sudo-dd",
        port=2192,
        hostname="bench-sudo-dd",
        family=FAMILY_SUDO,
        primitive="dd",
        description="NOPASSWD sudo for /bin/dd (GTFOBins read/write as root)",
        misconfig="sudo:/bin/dd",
    ),
    _t(
        id="sudo-bash-env",
        name="Bench · sudo BASH_ENV",
        service="bench-sudo-bash-env",
        port=2193,
        hostname="bench-sudo-bash-env",
        family=FAMILY_SUDO_ADVANCED,
        primitive="BASH_ENV",
        description="env_keep BASH_ENV + NOPASSWD bash",
        misconfig="sudo-bash-env",
    ),
    _t(
        id="sudo-perl5lib",
        name="Bench · sudo PERL5LIB",
        service="bench-sudo-perl5lib",
        port=2194,
        hostname="bench-sudo-perl5lib",
        family=FAMILY_SUDO_ADVANCED,
        primitive="PERL5LIB",
        description="env_keep PERL5LIB + NOPASSWD perl",
        misconfig="sudo-perl5lib",
    ),
    _t(
        id="suid-chmod",
        name="Bench · SUID chmod",
        service="bench-suid-chmod",
        port=2195,
        hostname="bench-suid-chmod",
        family=FAMILY_SUID,
        primitive="chmod",
        description="SUID bit on chmod (set SUID on /bin/bash)",
        misconfig="suid:chmod",
    ),
    _t(
        id="sudo-mv",
        name="Bench · sudo mv",
        service="bench-sudo-mv",
        port=2196,
        hostname="bench-sudo-mv",
        family=FAMILY_SUDO,
        primitive="mv",
        description="NOPASSWD mv replaces root-run hook in writable /opt/bench",
        misconfig="sudo-mv",
    ),
    _t(
        id="sudo-sed",
        name="Bench · sudo sed",
        service="bench-sudo-sed",
        port=2197,
        hostname="bench-sudo-sed",
        family=FAMILY_SUDO,
        primitive="sed",
        description="NOPASSWD sudo for /bin/sed (GTFOBins read as root)",
        misconfig="sudo:/bin/sed",
    ),
    _t(
        id="sudo-install",
        name="Bench · sudo install",
        service="bench-sudo-install",
        port=2198,
        hostname="bench-sudo-install",
        family=FAMILY_SUDO,
        primitive="install",
        description="NOPASSWD sudo for /usr/bin/install (copy+mode as root)",
        misconfig="sudo:/usr/bin/install",
    ),
    _t(
        id="suid-cp",
        name="Bench · SUID cp",
        service="bench-suid-cp",
        port=2199,
        hostname="bench-suid-cp",
        family=FAMILY_SUID,
        primitive="cp",
        description="SUID bit on cp (read protected files as root)",
        misconfig="suid:cp",
    ),
    _t(
        id="suid-dd",
        name="Bench · SUID dd",
        service="bench-suid-dd",
        port=2200,
        hostname="bench-suid-dd",
        family=FAMILY_SUID,
        primitive="dd",
        description="SUID bit on dd (read protected files as root)",
        misconfig="suid:dd",
    ),
    _t(
        id="suid-gawk",
        name="Bench · SUID gawk",
        service="bench-suid-gawk",
        port=2201,
        hostname="bench-suid-gawk",
        family=FAMILY_SUID,
        primitive="gawk",
        description="SUID bit on gawk (root execution via system/BEGIN)",
        misconfig="suid:gawk",
    ),
    _t(
        id="suid-env",
        name="Bench · SUID env",
        service="bench-suid-env",
        port=2202,
        hostname="bench-suid-env",
        family=FAMILY_SUID,
        primitive="env",
        description="SUID bit on env (spawn root shell)",
        misconfig="suid:env",
    ),
    _t(
        id="sudo-rubylib",
        name="Bench · sudo RUBYLIB",
        service="bench-sudo-rubylib",
        port=2223,
        hostname="bench-sudo-rubylib",
        family=FAMILY_SUDO_ADVANCED,
        primitive="RUBYLIB",
        description="env_keep RUBYLIB + NOPASSWD ruby",
        misconfig="sudo-rubylib",
    ),
    _t(
        id="suid-path-hijack",
        name="Bench · SUID PATH hijack",
        service="bench-suid-path-hijack",
        port=2224,
        hostname="bench-suid-path-hijack",
        family=FAMILY_SUID,
        primitive="system(benchhelper)",
        description="Custom SUID binary runs relative command (PATH hijack)",
        misconfig="suid-path-hijack",
    ),
    _t(
        id="suid-writable-exec",
        name="Bench · SUID writable helper",
        service="bench-suid-writable-exec",
        port=2225,
        hostname="bench-suid-writable-exec",
        family=FAMILY_SUID,
        primitive="/opt/bench/helper",
        description="Custom SUID binary execs world-writable absolute path",
        misconfig="suid-writable-exec",
    ),
    _t(
        id="wildcard-cron",
        name="Bench · wildcard cron",
        service="bench-wildcard-cron",
        port=2226,
        hostname="bench-wildcard-cron",
        family=FAMILY_WRITABLE,
        primitive="/opt/bench/wildcard/*",
        description="Root cron executes attacker scripts in lowpriv-owned dir",
        misconfig="wildcard-cron",
    ),
    _t(
        id="cred-shadow-read",
        name="Bench · readable shadow",
        service="bench-cred-shadow-read",
        port=2227,
        hostname="bench-cred-shadow-read",
        family=FAMILY_CREDENTIALS,
        primitive="/etc/shadow",
        description="World-readable /etc/shadow (su with known root password)",
        misconfig="cred-shadow-read",
    ),
    _t(
        id="sgid-secret",
        name="Bench · SGID group secret",
        service="bench-sgid-secret",
        port=2231,
        hostname="bench-sgid-secret",
        family=FAMILY_SGID,
        primitive="benchsecret",
        description="SGID cat reads group-owned copy of flag",
        misconfig="sgid-secret",
    ),
    _t(
        id="sudo-runas",
        name="Bench · sudo runas deploy",
        service="bench-sudo-runas",
        port=2234,
        hostname="bench-sudo-runas",
        family=FAMILY_SUDO_ADVANCED,
        primitive="(deploy)",
        description="NOPASSWD sudo as deploy user with root creds in home",
        misconfig="sudo-runas",
    ),
    _t(
        id="writable-ld-so-conf",
        name="Bench · writable ld.so.conf.d",
        service="bench-writable-ld-so-conf",
        port=2235,
        hostname="bench-writable-ld-so-conf",
        family=FAMILY_WRITABLE,
        primitive="/etc/ld.so.conf.d/bench.conf",
        description="Writable ld.so.conf.d entry + root ldconfig/id poller",
        misconfig="writable:ld-so-conf",
    ),
    _t(
        id="sudo-wildcard-tar",
        name="Bench · sudo tar wildcard",
        service="bench-sudo-wildcard-tar",
        port=2236,
        hostname="bench-sudo-wildcard-tar",
        family=FAMILY_SUDO_ADVANCED,
        primitive="tar *",
        description="NOPASSWD backup script with tar wildcard in attacker dir",
        misconfig="sudo-wildcard-tar",
    ),
    _t(
        id="logrotate-writable",
        name="Bench · writable logrotate hook",
        service="bench-logrotate-writable",
        port=2240,
        hostname="bench-logrotate-writable",
        family=FAMILY_WRITABLE,
        primitive="/opt/bench/logrotate-hook.sh",
        description="World-writable logrotate postrotate script",
        misconfig="logrotate-writable",
    ),
    _t(
        id="cred-core-dump",
        name="Bench · core dump secrets",
        service="bench-cred-core-dump",
        port=2241,
        hostname="bench-cred-core-dump",
        family=FAMILY_CREDENTIALS,
        primitive="/var/crash/bench-app.core",
        description="World-readable fake core dump with root password",
        misconfig="cred-core-dump",
    ),
    _t(
        id="suid-dlopen",
        name="Bench · SUID dlopen hijack",
        service="bench-suid-dlopen",
        port=2242,
        hostname="bench-suid-dlopen",
        family=FAMILY_SUID,
        primitive="dlopen payload",
        description="Custom SUID binary dlopen from writable directory",
        misconfig="suid-dlopen",
    ),
    _t(
        id="writable-motd",
        name="Bench · writable update-motd",
        service="bench-writable-motd",
        port=2243,
        hostname="bench-writable-motd",
        family=FAMILY_WRITABLE,
        primitive="/etc/update-motd.d/99-bench",
        description="World-writable motd hook run by root poller",
        misconfig="writable:motd",
    ),
    _t(
        id="sudo-git-hook",
        name="Bench · sudo git hook",
        service="bench-sudo-git-hook",
        port=2244,
        hostname="bench-sudo-git-hook",
        family=FAMILY_SUDO_ADVANCED,
        primitive="git hooks",
        description="NOPASSWD git commit runs planted pre-commit hook as root",
        misconfig="sudo-git-hook",
    ),
    _t(
        id="at-allow",
        name="Bench · writable at.allow",
        service="bench-at-allow",
        port=2245,
        hostname="bench-at-allow",
        family=FAMILY_WRITABLE,
        primitive="/etc/at.allow",
        description="World-writable at.allow schedules jobs as self then abuse",
        misconfig="at-allow",
    ),
    _t(
        id="ld-preload-script",
        name="Bench · LD_PRELOAD root script",
        service="bench-ld-preload-script",
        port=2246,
        hostname="bench-ld-preload-script",
        family=FAMILY_PATH,
        primitive="/opt/bench/rootwrap.sh",
        description="World-writable root wrapper exports LD_PRELOAD",
        misconfig="ld-preload-script",
    ),
    _t(
        id="screen-root-socket",
        name="Bench · root screen socket",
        service="bench-screen-root-socket",
        port=2247,
        hostname="bench-screen-root-socket",
        family=FAMILY_SHELL,
        primitive="screen multiuser",
        description="Root screen session with multiuser ACL for lowpriv",
        misconfig="screen-root-socket",
    ),
    _t(
        id="sudo-pip",
        name="Bench · sudo pip",
        service="bench-sudo-pip",
        port=2248,
        hostname="bench-sudo-pip",
        family=FAMILY_SUDO_ADVANCED,
        primitive="pip3",
        description="NOPASSWD pip3 install runs setup.py hooks as root",
        misconfig="sudo-pip",
    ),
    _t(
        id="writable-cron-allow",
        name="Bench · writable cron.allow",
        service="bench-writable-cron-allow",
        port=2249,
        hostname="bench-writable-cron-allow",
        family=FAMILY_WRITABLE,
        primitive="/etc/cron.allow",
        description="World-writable cron.allow + root cronjob hook poller",
        misconfig="writable-cron-allow",
    ),
    _t(
        id="sudo-gem",
        name="Bench · sudo gem",
        service="bench-sudo-gem",
        port=2250,
        hostname="bench-sudo-gem",
        family=FAMILY_SUDO_ADVANCED,
        primitive="gem",
        description="NOPASSWD gem install runs extconf/post_install hooks as root",
        misconfig="sudo-gem",
    ),
    _t(
        id="rbash-escape",
        name="Bench · rbash escape",
        service="bench-rbash-escape",
        port=2251,
        hostname="bench-rbash-escape",
        family=FAMILY_SHELL,
        primitive="/bin/rbash",
        description="Restricted shell + writable escape dir executed by root poller",
        misconfig="rbash-escape",
    ),
    _t(
        id="sudo-npm",
        name="Bench · sudo npm",
        service="bench-sudo-npm",
        port=2252,
        hostname="bench-sudo-npm",
        family=FAMILY_SUDO_ADVANCED,
        primitive="npm",
        description="NOPASSWD npm install runs lifecycle scripts as root",
        misconfig="sudo-npm",
    ),
    _t(
        id="writable-init-d",
        name="Bench · writable init.d",
        service="bench-writable-init-d",
        port=2253,
        hostname="bench-writable-init-d",
        family=FAMILY_WRITABLE,
        primitive="/etc/init.d/benchsvc",
        description="World-writable init script invoked by root poller",
        misconfig="writable-init-d",
    ),
]


def _target_ids(*families: str) -> List[str]:
    selected = set(families)
    return [target.id for target in TARGETS if target.family in selected]


PROFILES: List[BenchmarkProfile] = [
    BenchmarkProfile(
        id="does-it-work",
        name="Does it work?",
        description="Quick smoke test: sudo vim, sudo ALL, and sudo awk",
        target_ids=["sudo-vim", "sudo-all", "sudo-awk"],
    ),
    BenchmarkProfile(
        id="all-sudo-problems",
        name="All sudo problems",
        description="Every classic and advanced sudo misconfiguration",
        target_ids=_target_ids(FAMILY_SUDO, FAMILY_SUDO_ADVANCED),
    ),
    BenchmarkProfile(
        id="classic-sudo",
        name="Classic sudo commands",
        description="NOPASSWD command and GTFOBins-style sudo targets",
        target_ids=_target_ids(FAMILY_SUDO),
    ),
    BenchmarkProfile(
        id="advanced-sudo",
        name="Advanced sudo configuration",
        description="Environment, group, script, and authentication sudo issues",
        target_ids=_target_ids(FAMILY_SUDO_ADVANCED),
    ),
    BenchmarkProfile(
        id="suid",
        name="SUID binaries",
        description="Unsafe and writable SUID executables",
        target_ids=_target_ids(FAMILY_SUID),
    ),
    BenchmarkProfile(
        id="sgid",
        name="SGID binaries",
        description="SGID binaries and group-owned secrets",
        target_ids=_target_ids(FAMILY_SGID),
    ),
    BenchmarkProfile(
        id="writable",
        name="Writable files and loaders",
        description="Writable system files, root jobs, keys, and loader paths",
        target_ids=_target_ids(FAMILY_WRITABLE),
    ),
    BenchmarkProfile(
        id="capabilities",
        name="Linux capabilities",
        description="Dangerous file capabilities on interpreters",
        target_ids=_target_ids(FAMILY_CAPABILITIES),
    ),
    BenchmarkProfile(
        id="python-path",
        name="Python and PATH hijacks",
        description="Python import-path and executable PATH attacks",
        target_ids=_target_ids(FAMILY_PYTHON, FAMILY_PATH),
    ),
    BenchmarkProfile(
        id="credentials",
        name="Credential leaks",
        description="Keys, passwords, history, Ansible data, and logs",
        target_ids=_target_ids(FAMILY_CREDENTIALS),
    ),
    BenchmarkProfile(
        id="nfs",
        name="NFS detection",
        description="Detect-only NFS no_root_squash target",
        target_ids=_target_ids(FAMILY_NFS),
    ),
    BenchmarkProfile(
        id="services",
        name="Local network services",
        description="Misconfigured daemons reachable from lowpriv",
        target_ids=_target_ids(FAMILY_SERVICES),
    ),
    BenchmarkProfile(
        id="shell",
        name="Shell restrictions",
        description="Restricted shells and escape paths",
        target_ids=_target_ids(FAMILY_SHELL),
    ),
]


def list_targets() -> List[Dict[str, Any]]:
    return [t.to_dict() for t in TARGETS]


def list_profiles() -> List[Dict[str, Any]]:
    return [profile.to_dict() for profile in PROFILES]


def list_families() -> List[str]:
    seen: List[str] = []
    for t in TARGETS:
        if t.family not in seen:
            seen.append(t.family)
    return seen


def get_target(target_id: str) -> BenchmarkTarget:
    for target in TARGETS:
        if target.id == target_id:
            return target
    raise KeyError(f"Unknown benchmark target: {target_id}")


def resolve_targets(target_ids: Optional[List[str]] = None) -> List[BenchmarkTarget]:
    """
    Resolve a subset of suite targets.

    None means all targets. An empty list means no targets (caller validates).
    Unknown ids raise ValueError.
    """
    if target_ids is None:
        return list(TARGETS)

    seen: set[str] = set()
    ordered: List[str] = []
    for raw in target_ids:
        tid = str(raw or "").strip()
        if not tid or tid in seen:
            continue
        seen.add(tid)
        ordered.append(tid)

    if not ordered:
        return []

    known = {t.id: t for t in TARGETS}
    missing = [tid for tid in ordered if tid not in known]
    if missing:
        raise ValueError(f"Unknown benchmark target id(s): {', '.join(missing)}")
    return [known[tid] for tid in ordered]
