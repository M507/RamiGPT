"""Mutable runtime state shared across web modules (SSH sessions, AI loops)."""

from __future__ import annotations

import threading

# Shared stop flags for background tasks
stop_task_flag = threading.Event()
stop_full_ai = threading.Event()
stop_full_ai_by_session: dict[str, threading.Event] = {}

# When Full AI runs on a real OS thread (benchmark worker), socketio.sleep is unsafe.
_ai_tls = threading.local()

# SSH / prompt state keyed by inventory session id
ssh_shells: dict = {}
ssh_ssh_conns: dict = {}
prompt_delimiters: dict = {}
prompts: dict = {}
loop: dict = {}

# session_id -> monotonic epoch so stale shell_interaction tasks exit quietly
shell_listener_epoch: dict = {}

beroots: dict = {}
linenums: dict = {}
linpeas_reports: dict = {}
last_commands: dict = {}

# session_id -> history list stashed across disconnect/reconnect
_prompt_history_stash: dict = {}

# session_id -> True when Full AI detects root (benchmark + UI)
root_won_by_session: dict = {}

timeout_default = 6
prompt_delimiter = b"$ "
shell_recvuntil_v4_list: list = []
