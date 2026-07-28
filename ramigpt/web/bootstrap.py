"""One-time environment setup for the web layer (logging, pwntools, dirs)."""

from __future__ import annotations

import logging
import os
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("PWNLIB_NOTERM", "1")
logging.getLogger("pwnlib").setLevel(logging.ERROR)

from ramigpt.web.logging_config import configure_web_loggers

configure_web_loggers()

from pwn import *  # noqa: F403

context.log_level = "error"

from ramigpt.paths import ensure_runtime_dirs

ensure_runtime_dirs()
