"""Native Ollama provider (OpenAI-compatible ``/v1/chat/completions``)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

from openai import OpenAI

from ramigpt.ai.base import AIProvider, ChatMessage
from ramigpt.ai.providers.compat import (
    completion_text,
    ensure_suffix,
    make_openai_compat_client,
    usage_from_completion,
)
from ramigpt.config import Settings


def _ollama_origin(base_url: str) -> str:
    """Strip /v1 or /api suffixes so we can call native Ollama ``/api/tags``."""
    url = (base_url or "").strip().rstrip("/")
    for suffix in ("/v1", "/api"):
        if url.endswith(suffix):
            url = url[: -len(suffix)].rstrip("/")
            break
    return url


def _ollama_api_request(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    body: Optional[Dict[str, Any]] = None,
    timeout: float = 8.0,
) -> Dict[str, Any]:
    origin = _ollama_origin(base_url)
    if not origin:
        raise ValueError("Ollama base URL is empty")

    parsed = urlparse(origin if "://" in origin else f"http://{origin}")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid Ollama base URL: {base_url!r}")

    url = urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Ollama {path} HTTP {exc.code} at {url}") from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed Ollama {path} at {url}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected Ollama {path} payload from {url}")
    return payload


def list_ollama_models(base_url: str, *, timeout: float = 8.0) -> List[str]:
    """
    Fetch installed model names from an Ollama host via ``GET /api/tags``.

    Returns a de-duplicated, sorted list of model names (e.g. ``qwen3:14b``).
    """
    payload = _ollama_api_request(base_url, "/api/tags", timeout=timeout)
    models = payload.get("models")
    if not isinstance(models, list):
        raise RuntimeError("Unexpected Ollama /api/tags payload")

    names: List[str] = []
    seen = set()
    for item in models:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or item.get("model") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    names.sort(key=str.lower)
    return names


def ollama_model_names_match(expected: str, running: str) -> bool:
    """True when ``expected`` and ``running`` refer to the same Ollama model tag."""
    exp = (expected or "").strip().lower()
    run = (running or "").strip().lower()
    if not exp or not run:
        return False
    if exp == run:
        return True
    exp_base, _, exp_tag = exp.partition(":")
    run_base, _, run_tag = run.partition(":")
    if exp_base != run_base:
        return False
    if not exp_tag or not run_tag:
        return True
    return exp_tag == run_tag


def fetch_ollama_tag_info(base_url: str, model: str, *, timeout: float = 8.0) -> Dict[str, Any]:
    """Return the ``/api/tags`` entry for ``model`` (digest, size, modified_at, …)."""
    payload = _ollama_api_request(base_url, "/api/tags", timeout=timeout)
    models = payload.get("models")
    if not isinstance(models, list):
        raise RuntimeError("Unexpected Ollama /api/tags payload")

    target = (model or "").strip()
    for item in models:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or item.get("model") or "").strip()
        if name == target or ollama_model_names_match(target, name):
            return dict(item)
    raise RuntimeError(f"Model {target!r} not found in Ollama /api/tags")


def fetch_ollama_show(base_url: str, model: str, *, timeout: float = 12.0) -> Dict[str, Any]:
    """Fetch model metadata from ``POST /api/show``."""
    target = (model or "").strip()
    if not target:
        raise ValueError("Ollama model name is empty")
    return _ollama_api_request(
        base_url,
        "/api/show",
        method="POST",
        body={"name": target},
        timeout=timeout,
    )


def list_ollama_running_models(base_url: str, *, timeout: float = 8.0) -> List[str]:
    """Return model names currently loaded in Ollama memory (``GET /api/ps``)."""
    payload = _ollama_api_request(base_url, "/api/ps", timeout=timeout)
    models = payload.get("models")
    if not isinstance(models, list):
        raise RuntimeError("Unexpected Ollama /api/ps payload")

    names: List[str] = []
    seen = set()
    for item in models:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or item.get("model") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


class OllamaProvider(AIProvider):
    """Talks to Ollama's OpenAI-compatible API (default port 11434 → ``/v1``)."""

    def __init__(self, settings: Settings, client: Optional[OpenAI] = None) -> None:
        if not settings.ollama_base_url:
            raise ValueError("OLLAMA_BASE_URL is not configured.")

        base_url = ensure_suffix(settings.ollama_base_url, "/v1")
        api_key = settings.ollama_api_key or "ollama"
        self._client = make_openai_compat_client(
            api_key=api_key, base_url=base_url, client=client
        )
        self._model = settings.ollama_model
        self._base_url = base_url

    @property
    def name(self) -> str:
        return "ollama"

    def create_completion(self, messages: List[ChatMessage]) -> str:
        try:
            # Leave thinking enabled for capable models (e.g. qwen3). The
            # shared client timeout is raised so long reasoning traces can
            # finish before ``content`` is produced.
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
            )
        except Exception as exc:  # noqa: BLE001
            self.last_usage = None
            raise RuntimeError(
                f"AI provider ollama request failed at {self._base_url} "
                f"(model={self._model!r}): {exc}"
            ) from exc
        self.last_usage = usage_from_completion(completion)
        return completion_text(completion)
