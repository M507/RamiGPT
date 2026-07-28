#!/usr/bin/env python3
"""Ensure Ubuntu/Debian host packages for RamiGPT are installed.

Usage:
  python3 scripts/ensure_ubuntu_requirements.py
  python3 scripts/ensure_ubuntu_requirements.py --check-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from ramigpt.utils.ubuntu_requirements import (  # noqa: E402
    apt_install_hint,
    ensure_ubuntu_requirements,
    reset_ubuntu_requirements_cache,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Report missing packages without installing",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore process cache and re-check",
    )
    args = parser.parse_args()
    reset_ubuntu_requirements_cache()
    logs: list[str] = []

    def _log(msg: str) -> None:
        logs.append(msg)
        print(msg)

    try:
        result = ensure_ubuntu_requirements(
            install=not args.check_only,
            force=True,
            log=_log,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        print(f"Hint: {apt_install_hint()}", file=sys.stderr)
        return 1
    if result.message and result.message not in logs:
        print(result.message)
    if result.ansible_detail:
        print(f"Ansible: {result.ansible_detail}")
    for status in result.checked:
        mark = "OK" if status.present else "MISSING"
        print(
            f"  [{mark}] {status.requirement.package}: {status.detail} "
            f"— {status.requirement.reason}"
        )
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
