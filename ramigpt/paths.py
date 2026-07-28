"""Canonical filesystem paths for the project."""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent

CERTS_DIR = PROJECT_ROOT / "certs"
TOOLS_DIR = PROJECT_ROOT / "tools"
BEROOT_DIR = TOOLS_DIR / "beroot" / "Linux"
BEROOT_DOWNLOADS_DIR = BEROOT_DIR / "downloaded"
LINENUM_SCRIPT = TOOLS_DIR / "linenum" / "LinEnum.sh"
LINENUM_DOWNLOADS_DIR = TOOLS_DIR / "linenum" / "downloaded"
LINPEAS_SCRIPT = TOOLS_DIR / "linpeas" / "linpeas.sh"
LINPEAS_DOWNLOADS_DIR = TOOLS_DIR / "linpeas" / "downloaded"
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = DATA_DIR / "logs"
SESSIONS_DIR = DATA_DIR / "sessions"
SESSION_HOSTS_DIR = SESSIONS_DIR / "hosts"
SESSION_META_PATH = SESSIONS_DIR / "meta.json"
BENCHMARK_DIR = DATA_DIR / "benchmark"
BENCHMARK_REMOTE_CONFIG = BENCHMARK_DIR / "remote.json"
BENCHMARK_RESULTS_DIR = BENCHMARK_DIR / "results"
BENCHMARK_MODELS_DIR = BENCHMARK_DIR / "models"
SESSION_LOGS_DIR = LOGS_DIR / "sessions"
BENCHMARK_SESSION_LOGS_DIR = SESSION_LOGS_DIR / "benchmarks"
DOCS_DIR = PROJECT_ROOT / "docs"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
ENV_PATH = PROJECT_ROOT / ".env"
AI_SETTINGS_PATH = DATA_DIR / "ai_settings.json"
README_PATH = PROJECT_ROOT / "README.md"
BENCHMARK_MD_PATH = PROJECT_ROOT / "benchmark.md"

WEB_DIR = PACKAGE_DIR / "web"
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


def ensure_runtime_dirs() -> None:
    """Create directories needed at runtime."""
    for path in (
        LOGS_DIR,
        SESSION_LOGS_DIR,
        BENCHMARK_SESSION_LOGS_DIR,
        SESSIONS_DIR,
        SESSION_HOSTS_DIR,
        BENCHMARK_DIR,
        BENCHMARK_RESULTS_DIR,
        BENCHMARK_MODELS_DIR,
        BEROOT_DOWNLOADS_DIR,
        LINENUM_DOWNLOADS_DIR,
        LINPEAS_DOWNLOADS_DIR,
        CERTS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
