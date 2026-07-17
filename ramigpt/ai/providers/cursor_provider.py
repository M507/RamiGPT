"""
Cursor Cloud Agents provider.

Docs: https://cursor.com/docs/cloud-agent/api/endpoints

Unlike the other providers, the Cursor Cloud Agents API is asynchronous:
creating an agent enqueues a run that must be polled until it reaches a
terminal status. To stay compatible with the synchronous
``AIProvider.create_completion`` contract used everywhere else in RamiGPT,
each call here creates a fresh, repo-less agent (no ``repos``/``env`` —
see "no-repo agent" in the API docs), polls its initial run to completion,
and returns the run's final ``result`` text. The agent is archived
afterwards so pentest loops (which may call this many times) don't pile up
agents in the Cursor dashboard.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from ramigpt.ai.base import AIProvider, ChatMessage
from ramigpt.config import Settings

DEFAULT_BASE_URL = "https://api.cursor.com"
# Must match an id from GET /v1/models (composer-2 is obsolete; composer-2.5 is current).
DEFAULT_MODEL = "composer-2.5"

_TERMINAL_STATUSES = {"FINISHED", "ERROR", "CANCELLED", "EXPIRED"}
_POLL_INTERVAL_START_S = 2.0
_POLL_INTERVAL_MAX_S = 8.0
_POLL_TIMEOUT_S = 480.0
_REQUEST_TIMEOUT_S = 30.0
# Creating a cloud agent often waits on VM provisioning and can exceed 60s.
_CREATE_TIMEOUT_S = 120.0
# Treat these as "use Cursor's account default" — omit model from the body.
_DEFAULT_MODEL_ALIASES = {"", "default", "auto"}


def _basic_auth_header(api_key: str) -> str:
    # Docs use `-u YOUR_API_KEY:` — API key as Basic-auth username, empty password.
    token = base64.b64encode(f"{api_key}:".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _request(
    method: str,
    url: str,
    api_key: str,
    *,
    body: Optional[Dict[str, Any]] = None,
    timeout: float = _REQUEST_TIMEOUT_S,
) -> Dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", _basic_auth_header(api_key))
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise RuntimeError(
            f"Cursor API {method} {url} -> HTTP {exc.code}: {detail or exc.reason}"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Cursor API {method} {url} failed: {exc}") from exc

    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Cursor API {method} {url} returned invalid JSON: {exc}") from exc


def list_cursor_models(
    api_key: str, *, base_url: str = DEFAULT_BASE_URL, timeout: float = 8.0
) -> List[str]:
    """Fetch recommended model ids from ``GET /v1/models``."""
    return [item["id"] for item in list_cursor_model_details(api_key, base_url=base_url, timeout=timeout)]


def _cursor_model_cost_rank(model_id: str) -> int:
    """
    Heuristic cost rank for UI sorting (higher = more expensive).

    Cursor's ``/v1/models`` does not return prices, so we bucket by family.
    """
    mid = (model_id or "").strip().lower().replace("_", "-")
    tokens = {part for part in mid.replace(".", "-").split("-") if part}

    def has(*needles: str) -> bool:
        return any(needle in tokens or needle in mid for needle in needles)

    def has_token(*needles: str) -> bool:
        return any(needle in tokens for needle in needles)

    if mid in {"default", "auto"} or has_token("default", "auto"):
        return 0
    if has_token("opus") or "opus" in mid:
        return 1000
    if has_token("fable") or "fable" in mid:
        return 950
    if has_token("sonnet") or "sonnet" in mid:
        return 850

    is_mini = has_token("mini", "nano")
    if has("gpt-5.6", "gpt-5-6") or ("gpt" in tokens and "5" in tokens and "6" in tokens):
        return 350 if is_mini else 800
    if any(tag in mid for tag in ("gpt-5.5", "gpt-5-5", "gpt-5.4", "gpt-5-4", "gpt-5.3", "gpt-5-3", "gpt-5.2", "gpt-5-2", "gpt-5.1", "gpt-5-1")):
        if is_mini:
            return 340
        if has_token("codex") or "codex" in mid:
            return 650
        return 750
    if mid.startswith("gpt-5") and not is_mini:
        return 700
    if has_token("composer", "codex") or "composer" in mid or "codex" in mid:
        return 600
    if has_token("gemini") and has_token("pro"):
        return 550
    if has_token("grok") or "grok" in mid:
        return 500
    if has_token("kimi") or mid.startswith("glm") or has_token("glm"):
        return 450
    if is_mini:
        return 300
    if has_token("haiku") or "haiku" in mid:
        return 250
    if has_token("flash") or "flash" in mid:
        return 200
    return 400


def _sort_cursor_models(models: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Sort most costly → cheapest; keep Auto/default last."""
    return sorted(
        models,
        key=lambda item: (
            _cursor_model_cost_rank(item.get("id", "")),
            (item.get("displayName") or item.get("id") or "").lower(),
        ),
        reverse=True,
    )


def list_cursor_model_details(
    api_key: str, *, base_url: str = DEFAULT_BASE_URL, timeout: float = 8.0
) -> List[Dict[str, str]]:
    """
    Fetch recommended models from ``GET /v1/models``.

    Each entry is ``{"id": "...", "displayName": "..."}`` for the Settings UI.
    Results are ordered most costly → cheapest. ``default`` (Auto) is always
    included as a cheap account-default option.
    """
    if not api_key:
        raise ValueError("Cursor API key is empty")

    url = f"{(base_url or DEFAULT_BASE_URL).rstrip('/')}/v1/models"
    payload = _request("GET", url, api_key, timeout=timeout)
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise RuntimeError(f"Unexpected Cursor /v1/models payload from {url}")

    models: List[Dict[str, str]] = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        model_id = (item.get("id") or "").strip()
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        display = (item.get("displayName") or model_id).strip() or model_id
        if model_id.lower() in {"default", "auto"}:
            display = "Auto (cheap / account default)"
        models.append({"id": model_id, "displayName": display})

    # Always expose Auto even if the API response somehow omits it.
    if "default" not in seen and "auto" not in seen:
        models.append(
            {"id": "default", "displayName": "Auto (cheap / account default)"}
        )

    return _sort_cursor_models(models)


def _build_prompt_text(messages: List[ChatMessage]) -> str:
    """
    Flatten a chat-style message list into the single ``prompt.text`` field
    the Cloud Agents API expects. RamiGPT's prompts already embed the full
    running context in the user message, so this is a light label-and-join
    rather than a true multi-turn transcript.
    """
    parts: List[str] = []
    for message in messages:
        role = (message.get("role") or "user").strip().lower()
        content = (message.get("content") or "").strip()
        if not content:
            continue
        if role == "system":
            parts.append(content)
        elif role == "assistant":
            parts.append(f"Assistant: {content}")
        else:
            parts.append(content)
    return "\n\n".join(parts).strip()


class CursorProvider(AIProvider):
    """Runs prompts through Cursor's Cloud Agents API (v1) as no-repo agents."""

    def __init__(self, settings: Settings) -> None:
        if not settings.cursor_api_key:
            raise ValueError("CURSOR_API_KEY is not configured.")
        self._api_key = settings.cursor_api_key
        raw_model = (settings.cursor_model or DEFAULT_MODEL).strip()
        # Map the obsolete docs example id to the current recommended Composer.
        if raw_model == "composer-2":
            raw_model = DEFAULT_MODEL
        self._model = raw_model
        self._base_url = (settings.cursor_base_url or DEFAULT_BASE_URL).rstrip("/")

    @property
    def name(self) -> str:
        return "cursor"

    def create_completion(self, messages: List[ChatMessage]) -> str:
        prompt_text = _build_prompt_text(messages)
        if not prompt_text:
            raise RuntimeError("Cursor provider received an empty prompt.")

        body: Dict[str, Any] = {"prompt": {"text": prompt_text}}
        model_id = self._model.strip().lower() if self._model else ""
        if model_id not in _DEFAULT_MODEL_ALIASES:
            body["model"] = {"id": self._model}

        try:
            created = _request(
                "POST",
                f"{self._base_url}/v1/agents",
                self._api_key,
                body=body,
                timeout=_CREATE_TIMEOUT_S,
            )
        except Exception as exc:  # noqa: BLE001
            self.last_usage = None
            raise RuntimeError(
                f"AI provider cursor request failed to create agent "
                f"(model={self._model!r}): {exc}"
            ) from exc

        agent = created.get("agent") or {}
        run = created.get("run") or {}
        agent_id = agent.get("id")
        run_id = run.get("id")
        if not agent_id or not run_id:
            self.last_usage = None
            raise RuntimeError(f"Cursor API did not return an agent/run id: {created!r}")

        # Create can return an already-finished run (fast cloud starts).
        status = (run.get("status") or "").upper()
        try:
            if status == "FINISHED" and run.get("result") is not None:
                result_text = run.get("result") or ""
                usage = self._fetch_usage(agent_id, run_id)
            else:
                result_text, usage = self._await_run(agent_id, run_id)
        except Exception as exc:  # noqa: BLE001
            self.last_usage = None
            raise RuntimeError(
                f"AI provider cursor run {run_id} failed (agent={agent_id}): {exc}"
            ) from exc
        finally:
            self._archive(agent_id)

        self.last_usage = usage
        return (result_text or "").strip()

    def _await_run(
        self, agent_id: str, run_id: str
    ) -> Tuple[str, Optional[Dict[str, int]]]:
        url = f"{self._base_url}/v1/agents/{agent_id}/runs/{run_id}"
        deadline = time.monotonic() + _POLL_TIMEOUT_S
        interval = _POLL_INTERVAL_START_S
        while True:
            run = _request("GET", url, self._api_key, timeout=_REQUEST_TIMEOUT_S)
            status = (run.get("status") or "").upper()
            if status in _TERMINAL_STATUSES:
                if status != "FINISHED":
                    raise RuntimeError(
                        f"run ended with status {status}: {run.get('result') or ''}".strip()
                    )
                return run.get("result") or "", self._fetch_usage(agent_id, run_id)
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"run did not finish within {_POLL_TIMEOUT_S:.0f}s "
                    f"(last status: {status or 'unknown'})"
                )
            time.sleep(interval)
            interval = min(interval * 1.5, _POLL_INTERVAL_MAX_S)

    def _fetch_usage(self, agent_id: str, run_id: str) -> Optional[Dict[str, int]]:
        try:
            payload = _request(
                "GET",
                f"{self._base_url}/v1/agents/{agent_id}/usage?runId={run_id}",
                self._api_key,
                timeout=15.0,
            )
        except Exception:  # noqa: BLE001
            return None

        usage = (payload or {}).get("totalUsage")
        if not isinstance(usage, dict):
            return None

        result: Dict[str, int] = {}
        input_tokens = usage.get("inputTokens")
        output_tokens = usage.get("outputTokens")
        total_tokens = usage.get("totalTokens")
        if isinstance(input_tokens, int):
            result["prompt_tokens"] = input_tokens
        if isinstance(output_tokens, int):
            result["completion_tokens"] = output_tokens
        if isinstance(total_tokens, int):
            result["total_tokens"] = total_tokens
        elif isinstance(input_tokens, int) and isinstance(output_tokens, int):
            result["total_tokens"] = input_tokens + output_tokens
        return result or None

    def _archive(self, agent_id: str) -> None:
        """Best-effort cleanup; never fails the caller."""
        try:
            _request(
                "POST",
                f"{self._base_url}/v1/agents/{agent_id}/archive",
                self._api_key,
                body={},
                timeout=10.0,
            )
        except Exception:  # noqa: BLE001
            pass
