"""Application configuration loaded from environment / .env, with runtime updates."""

from __future__ import annotations

import os
import threading
from dataclasses import asdict, dataclass, fields
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from ramigpt.paths import ENV_PATH

# Keys persisted to .env when settings are saved from the UI
PERSISTED_KEYS = (
    "AI_PROVIDER",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_BASE_URL",
    "OLLAMA_BASE_URL",
    "OLLAMA_API_KEY",
    "OLLAMA_MODEL",
    "OPENWEBUI_BASE_URL",
    "OPENWEBUI_API_KEY",
    "OPENWEBUI_MODEL",
    "OPENAI_MAX_NUM_OF_REQS",
    "DEBUG",
)

VALID_PROVIDERS = ("openai", "ollama", "openwebui")


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
    openai_max_num_of_reqs: int = 10
    debug: int = 0

    def active_api_key(self) -> str:
        if self.ai_provider == "ollama":
            return self.ollama_api_key or "ollama"
        if self.ai_provider == "openwebui":
            return self.openwebui_api_key or self.openai_api_key
        return self.openai_api_key

    def active_model(self) -> str:
        if self.ai_provider == "ollama":
            return self.ollama_model
        if self.ai_provider == "openwebui":
            return self.openwebui_model
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
        openai_max_num_of_reqs=_env_int("OPENAI_MAX_NUM_OF_REQS", 10),
        debug=_env_int("DEBUG", 0),
    )


class SettingsManager:
    """Thread-safe settings holder with optional .env persistence."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._settings = _load_settings_from_env()

    @property
    def settings(self) -> Settings:
        with self._lock:
            return self._settings

    def reload(self) -> Settings:
        with self._lock:
            self._settings = _load_settings_from_env()
            return self._settings

    def update(self, updates: Dict[str, Any], persist: bool = True) -> Settings:
        """Apply partial updates. Empty API-key fields keep the existing secret."""
        with self._lock:
            data = asdict(self._settings)
            field_names = {f.name for f in fields(Settings)}

            for key, value in updates.items():
                if key not in field_names:
                    continue
                if key in ("openai_api_key", "ollama_api_key", "openwebui_api_key"):
                    if value is None:
                        continue
                    if isinstance(value, str) and (
                        value.strip() == "" or "..." in value or value.startswith("*")
                    ):
                        # Keep existing key when the UI sends a masked/empty value
                        continue
                if key == "ai_provider":
                    value = _normalize_provider(str(value))
                    if value not in VALID_PROVIDERS:
                        raise ValueError(f"Invalid AI provider: {value}")
                if key in ("openai_max_num_of_reqs", "debug"):
                    value = int(value)
                if key in ("ollama_base_url", "openwebui_base_url") and isinstance(value, str):
                    value = value.strip().rstrip("/")
                data[key] = value

            self._settings = Settings(**data)
            if persist:
                self._write_env(self._settings)
            return self._settings

    def _write_env(self, settings: Settings) -> None:
        existing: Dict[str, str] = {}
        if ENV_PATH.exists():
            for line in ENV_PATH.read_text().splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                existing[key.strip()] = value.strip()

        mapping = {
            "AI_PROVIDER": settings.ai_provider,
            "OPENAI_API_KEY": settings.openai_api_key,
            "OPENAI_MODEL": settings.openai_model,
            "OPENAI_BASE_URL": settings.openai_base_url,
            "OLLAMA_BASE_URL": settings.ollama_base_url,
            "OLLAMA_API_KEY": settings.ollama_api_key,
            "OLLAMA_MODEL": settings.ollama_model,
            "OPENWEBUI_BASE_URL": settings.openwebui_base_url,
            "OPENWEBUI_API_KEY": settings.openwebui_api_key,
            "OPENWEBUI_MODEL": settings.openwebui_model,
            "OPENAI_MAX_NUM_OF_REQS": str(settings.openai_max_num_of_reqs),
            "DEBUG": str(settings.debug),
        }
        existing.update(mapping)

        lines = [f"{key}={existing[key]}" for key in PERSISTED_KEYS if key in existing]
        # Preserve any other unrelated keys
        for key, value in existing.items():
            if key not in PERSISTED_KEYS:
                lines.append(f"{key}={value}")

        ENV_PATH.write_text("\n".join(lines) + "\n")
        # Keep process env in sync for anything still reading os.getenv
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
