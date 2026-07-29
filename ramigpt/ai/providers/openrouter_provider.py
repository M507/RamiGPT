"""OpenRouter chat-completions provider (official ``openrouter`` SDK)."""

from __future__ import annotations

from typing import Any, List, Optional

from openrouter import OpenRouter

from ramigpt.ai.base import AIProvider, ChatMessage
from ramigpt.config import Settings

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_HTTP_REFERER = "https://github.com/M507/RamiGPT"
DEFAULT_APP_TITLE = "RamiGPT"
# Cloud models can still sit on long prompts / reasoning; match local compat budget.
_DEFAULT_TIMEOUT_MS = 600_000


def openrouter_base_url(base_url: str = "") -> str:
    """Normalize an OpenRouter API root (defaults to the public ``/api/v1`` endpoint)."""
    url = (base_url or "").strip().rstrip("/")
    if not url:
        return DEFAULT_BASE_URL
    if url.endswith("/api/v1"):
        return url
    if url.endswith("/api"):
        return f"{url}/v1"
    if url.endswith("/v1"):
        return url
    return f"{url}/api/v1"


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
            else:
                text = getattr(item, "text", None) or getattr(item, "content", None)
                if text:
                    parts.append(str(text))
        return "".join(parts)
    return str(value)


def _message_text(message: Any) -> str:
    content = _coerce_text(getattr(message, "content", None)).strip()
    if content:
        return content
    for attr in ("reasoning", "refusal"):
        fallback = _coerce_text(getattr(message, attr, None)).strip()
        if fallback:
            return fallback
    return ""


def _usage_from_result(result: Any) -> Optional[dict]:
    usage = getattr(result, "usage", None)
    if usage is None:
        return None

    def _get(name: str) -> Optional[int]:
        val = getattr(usage, name, None)
        try:
            return int(val) if val is not None else None
        except (TypeError, ValueError):
            return None

    prompt_tokens = _get("prompt_tokens")
    completion_tokens = _get("completion_tokens")
    total_tokens = _get("total_tokens")
    if prompt_tokens is None and completion_tokens is None and total_tokens is None:
        return None

    out: dict = {}
    if prompt_tokens is not None:
        out["prompt_tokens"] = prompt_tokens
    if completion_tokens is not None:
        out["completion_tokens"] = completion_tokens
    if total_tokens is not None:
        out["total_tokens"] = total_tokens
    elif prompt_tokens is not None and completion_tokens is not None:
        out["total_tokens"] = prompt_tokens + completion_tokens
    return out or None


def make_openrouter_client(
    *,
    api_key: str,
    base_url: str = "",
    client: Optional[OpenRouter] = None,
    timeout_ms: int = _DEFAULT_TIMEOUT_MS,
) -> OpenRouter:
    if client is not None:
        return client
    kwargs: dict = {
        "api_key": api_key,
        "http_referer": DEFAULT_HTTP_REFERER,
        "x_open_router_title": DEFAULT_APP_TITLE,
        "timeout_ms": timeout_ms,
    }
    resolved = openrouter_base_url(base_url)
    if resolved != DEFAULT_BASE_URL:
        kwargs["server_url"] = resolved
    return OpenRouter(**kwargs)


def list_openrouter_models(
    api_key: str,
    *,
    base_url: str = "",
    timeout: float = 8.0,
) -> List[str]:
    """Return model ids from OpenRouter (``GET /models`` via the official SDK)."""
    if not (api_key or "").strip():
        raise ValueError("OpenRouter API key is not configured")
    client = make_openrouter_client(
        api_key=api_key.strip(),
        base_url=base_url,
        timeout_ms=max(1, int(timeout * 1000)),
    )
    response = client.models.list()
    result = getattr(response, "result", None)
    data = getattr(result, "data", None) if result is not None else None
    names: List[str] = []
    for item in data or []:
        model_id = getattr(item, "id", None)
        if model_id:
            names.append(str(model_id))
    return sorted(set(names), key=str.lower)


class OpenRouterProvider(AIProvider):
    """Chat completions through OpenRouter's multi-model gateway."""

    def __init__(self, settings: Settings, client: Optional[OpenRouter] = None) -> None:
        if not settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is not configured.")

        self._base_url = openrouter_base_url(settings.openrouter_base_url)
        self._client = make_openrouter_client(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            client=client,
        )
        self._model = settings.openrouter_model

    @property
    def name(self) -> str:
        return "openrouter"

    def create_completion(self, messages: List[ChatMessage]) -> str:
        try:
            result = self._client.chat.send(
                model=self._model,
                messages=messages,
                stream=False,
            )
        except Exception as exc:  # noqa: BLE001
            self.last_usage = None
            raise RuntimeError(
                f"AI provider openrouter request failed at {self._base_url} "
                f"(model={self._model!r}): {exc}"
            ) from exc

        self.last_usage = _usage_from_result(result)
        if result is None:
            raise RuntimeError(
                f"AI provider openrouter returned an empty HTTP body (null) at "
                f"{self._base_url} (model={self._model!r})."
            )
        choices = getattr(result, "choices", None)
        if not choices:
            raise RuntimeError(
                f"AI provider openrouter returned no choices at {self._base_url} "
                f"(model={self._model!r})."
            )
        text = _message_text(choices[0].message)
        if not text.strip():
            raise RuntimeError(
                f"AI provider openrouter returned an empty message at "
                f"{self._base_url} (model={self._model!r})."
            )
        return text.strip()
