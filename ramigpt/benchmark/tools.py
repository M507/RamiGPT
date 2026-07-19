"""Tools that can run before Full AI during a benchmark target."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Ids must match tool selector / POST /action3 "tool" values (e.g. BeRoot → "beroot").
AVAILABLE_TOOLS: List[Dict[str, Any]] = [
    {
        "id": "beroot",
        "name": "BeRoot",
        "description": "Upload & scan, then Full AI uses findings until root",
        "default": True,
    },
    {
        "id": "linenum",
        "name": "LinEnum",
        "description": "Upload & run LinEnum.sh (-t), then Full AI uses findings until root",
        "default": False,
    },
    {
        "id": "linpeas",
        "name": "LinPEAS",
        "description": "Upload & run linpeas.sh (fast mode, -P), then Full AI uses findings until root",
        "default": False,
    },
]

# When multiple pre-tools are checked, only the first in this list runs per target.
TOOL_RUN_ORDER: List[str] = [t["id"] for t in AVAILABLE_TOOLS]


def default_tools() -> Dict[str, bool]:
    return {t["id"]: bool(t.get("default")) for t in AVAILABLE_TOOLS}


def normalize_tools(raw: Any) -> Dict[str, bool]:
    """
    Accept:
      - {"beroot": true}
      - ["beroot"]
      - null / missing → defaults (BeRoot on)
    Unknown ids are ignored.
    """
    defaults = default_tools()
    if raw is None:
        return defaults
    if isinstance(raw, dict):
        out = {k: False for k in defaults}
        for key, val in raw.items():
            kid = str(key).strip().lower()
            if kid in out:
                if isinstance(val, str):
                    out[kid] = val.strip().lower() not in {"0", "false", "no", "off", ""}
                else:
                    out[kid] = bool(val)
        return out
    if isinstance(raw, (list, tuple, set)):
        out = {k: False for k in defaults}
        for item in raw:
            kid = str(item).strip().lower()
            if kid in out:
                out[kid] = True
        return out
    return defaults


def enabled_tool_ids(tools: Dict[str, bool]) -> List[str]:
    return [tid for tid, on in (tools or {}).items() if on]


def pick_benchmark_tool(tools: Dict[str, bool]) -> Optional[str]:
    """Return the single pre-tool to run for a benchmark target, if any."""
    enabled = set(enabled_tool_ids(tools))
    for tid in TOOL_RUN_ORDER:
        if tid in enabled:
            return tid
    return None
