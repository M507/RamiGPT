"""Application settings loaded from environment secrets and JSON user choices."""

from __future__ import annotations

import json
import os
import threading
import warnings
from dataclasses import asdict, dataclass, fields
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from ramigpt.paths import AI_SETTINGS_PATH, ENV_PATH

# Secrets stay in .env. User-selectable, non-secret values are persisted in
# data/ai_settings.json so switching providers never rewrites .env.
SECRET_FIELDS = (
    "openai_api_key",
    "ollama_api_key",
    "openwebui_api_key",
    "cursor_api_key",
)
JSON_SETTING_FIELDS = (
    "ai_provider",
    "openai_model",
    "openai_base_url",
    "ollama_base_url",
    "ollama_model",
    "openwebui_base_url",
    "openwebui_model",
    "cursor_model",
    "cursor_base_url",
    "openai_max_num_of_reqs",
    "debug",
)

VALID_PROVIDERS = ("openai", "ollama", "openwebui", "cursor")


@dataclass
class Settings:
    """Runtime AI and app settings."""

    ai_provider: str = "ollama"
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"
    openai_base_url: str = ""  # empty → OpenAI default
    ollama_base_url: str = "http://10.10.10.82:11434"
    ollama_api_key: str = "ollama"
    ollama_model: str = "qwen3:14b"
    openwebui_base_url: str = "http://localhost:3000"
    openwebui_api_key: str = ""
    openwebui_model: str = "llama3.1"
    cursor_api_key: str = ""
    cursor_model: str = "composer-2.5"
    cursor_base_url: str = ""  # empty → https://api.cursor.com
    openai_max_num_of_reqs: int = 10
    debug: int = 0

    def active_api_key(self) -> str:
        if self.ai_provider == "ollama":
            return self.ollama_api_key or "ollama"
        if self.ai_provider == "openwebui":
            return self.openwebui_api_key or self.openai_api_key
        if self.ai_provider == "cursor":
            return self.cursor_api_key
        return self.openai_api_key

    def active_model(self) -> str:
        if self.ai_provider == "ollama":
            return self.ollama_model
        if self.ai_provider == "openwebui":
            return self.openwebui_model
        if self.ai_provider == "cursor":
            return self.cursor_model
        return self.openai_model

    def to_public_dict(self) -> Dict[str, Any]:
        """Serialize for the settings UI; mask secrets."""
        return {
            "ai_provider": self.ai_provider,
            "openai_api_key": _mask_secret(self.openai_api_key),
            "openai_api_key_set": bool(self.openai_api_key),
            "openai_model": self.openai_model,
            "openai_base_url": self.openai_base_url,
            "ollama_base_url": self.ollama_base_url,
            "ollama_api_key": _mask_secret(self.ollama_api_key),
            "ollama_api_key_set": bool(self.ollama_api_key),
            "ollama_model": self.ollama_model,
            "openwebui_base_url": self.openwebui_base_url,
            "openwebui_api_key": _mask_secret(self.openwebui_api_key),
            "openwebui_api_key_set": bool(self.openwebui_api_key),
            "openwebui_model": self.openwebui_model,
            "cursor_api_key": _mask_secret(self.cursor_api_key),
            "cursor_api_key_set": bool(self.cursor_api_key),
            "cursor_model": self.cursor_model,
            "cursor_base_url": self.cursor_base_url,
            "openai_max_num_of_reqs": self.openai_max_num_of_reqs,
            "debug": self.debug,
            "providers": list(VALID_PROVIDERS),
        }


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _normalize_provider(raw: str) -> str:
    provider = (raw or "ollama").strip().lower()
    if provider not in VALID_PROVIDERS:
        return "ollama"
    return provider


def _load_settings_from_env() -> Settings:
    load_dotenv(ENV_PATH, override=True)
    provider = _normalize_provider(os.getenv("AI_PROVIDER") or "ollama")

    # Migrate older setups that used openwebui_* for a bare Ollama :11434 endpoint.
    ollama_base = (os.getenv("OLLAMA_BASE_URL") or "").strip().rstrip("/")
    ollama_key = (os.getenv("OLLAMA_API_KEY") or "").strip().strip('"')
    ollama_model = (os.getenv("OLLAMA_MODEL") or "").strip()
    owu_base = (os.getenv("OPENWEBUI_BASE_URL") or "").strip().rstrip("/")
    if not ollama_base and (":11434" in owu_base or owu_base.endswith("/v1")):
        ollama_base = owu_base
        if not ollama_key:
            ollama_key = (os.getenv("OPENWEBUI_API_KEY") or "ollama").strip().strip('"')
        if not ollama_model:
            ollama_model = (os.getenv("OPENWEBUI_MODEL") or "").strip()
        if provider == "openwebui":
            provider = "ollama"

    return Settings(
        ai_provider=provider,
        openai_api_key=(os.getenv("OPENAI_API_KEY") or "").strip().strip('"'),
        openai_model=(os.getenv("OPENAI_MODEL") or "gpt-5-mini").strip(),
        openai_base_url=(os.getenv("OPENAI_BASE_URL") or "").strip(),
        ollama_base_url=ollama_base or "http://10.10.10.82:11434",
        ollama_api_key=ollama_key or "ollama",
        ollama_model=ollama_model or "qwen3:14b",
        openwebui_base_url=owu_base or "http://localhost:3000",
        openwebui_api_key=(os.getenv("OPENWEBUI_API_KEY") or "").strip().strip('"'),
        openwebui_model=(os.getenv("OPENWEBUI_MODEL") or "llama3.1").strip(),
        cursor_api_key=(os.getenv("CURSOR_API_KEY") or "").strip().strip('"'),
        cursor_model=(os.getenv("CURSOR_MODEL") or "composer-2.5").strip(),
        cursor_base_url=(os.getenv("CURSOR_BASE_URL") or "").strip().rstrip("/"),
        openai_max_num_of_reqs=_env_int("OPENAI_MAX_NUM_OF_REQS", 10),
        debug=_env_int("DEBUG", 0),
    )


def _apply_updates(settings: Settings, updates: Dict[str, Any]) -> Settings:
    data = asdict(settings)
    field_names = {f.name for f in fields(Settings)}

    for key, value in updates.items():
        if key not in field_names:
            continue
        if key in SECRET_FIELDS:
            if value is None:
                continue
            if isinstance(value, str) and (
                value.strip() == "" or "..." in value or value.startswith("*")
            ):
                # Keep the existing key when the UI sends a masked/empty value.
                continue
        if key == "ai_provider":
            value = str(value).strip().lower()
            if value not in VALID_PROVIDERS:
                raise ValueError(f"Invalid AI provider: {value}")
        if key in ("openai_max_num_of_reqs", "debug"):
            value = int(value)
        if key in (
            "ollama_base_url",
            "openwebui_base_url",
            "cursor_base_url",
        ) and isinstance(value, str):
            value = value.strip().rstrip("/")
        data[key] = value

    return Settings(**data)


def _load_settings() -> Settings:
    settings = _load_settings_from_env()
    if not AI_SETTINGS_PATH.exists():
        return settings

    try:
        payload = json.loads(AI_SETTINGS_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("top-level value must be an object")
        updates = {
            key: payload[key]
            for key in JSON_SETTING_FIELDS
            if key in payload
        }
        return _apply_updates(settings, updates)
    except Exception as exc:  # noqa: BLE001
        warnings.warn(
            f"Ignoring invalid AI settings file {AI_SETTINGS_PATH}: {exc}",
            RuntimeWarning,
            stacklevel=2,
        )
        return settings


class SettingsManager:
    """Thread-safe settings holder with JSON choices and .env secrets."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._settings = _load_settings()

    @property
    def settings(self) -> Settings:
        with self._lock:
            return self._settings

    def reload(self) -> Settings:
        with self._lock:
            self._settings = _load_settings()
            return self._settings

    def update(self, updates: Dict[str, Any], persist: bool = True) -> Settings:
        """Apply partial updates. Empty API-key fields keep the existing secret."""
        with self._lock:
            self._settings = _apply_updates(self._settings, updates)
            if persist:
                self._write_json(self._settings)
                self._write_env_secrets(self._settings)
            return self._settings

    def _write_json(self, settings: Settings) -> None:
        payload = {
            key: getattr(settings, key)
            for key in JSON_SETTING_FIELDS
        }
        AI_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporary = AI_SETTINGS_PATH.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(AI_SETTINGS_PATH)

    def _write_env_secrets(self, settings: Settings) -> None:
        mapping = {
            "OPENAI_API_KEY": settings.openai_api_key,
            "OLLAMA_API_KEY": settings.ollama_api_key,
            "OPENWEBUI_API_KEY": settings.openwebui_api_key,
            "CURSOR_API_KEY": settings.cursor_api_key,
        }

        lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
        written = set()
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in line:
                continue
            key = line.partition("=")[0].strip()
            if key in mapping:
                lines[index] = f"{key}={mapping[key]}"
                written.add(key)
        for key, value in mapping.items():
            if key not in written:
                lines.append(f"{key}={value}")

        ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
        ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        for key, value in mapping.items():
            os.environ[key] = value


_manager: Optional[SettingsManager] = None


def get_settings_manager() -> SettingsManager:
    global _manager
    if _manager is None:
        _manager = SettingsManager()
    return _manager


def get_settings() -> Settings:
    return get_settings_manager().settings
