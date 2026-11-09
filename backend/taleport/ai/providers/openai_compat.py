"""Providers with an OpenAI-style HTTP API.

- Chat Completions (`/chat/completions`): OpenAI, xAI, Google Gemini (OpenAI compatibility).
- Responses-style (`/responses`, Perplexity's `/v1/agent`): Perplexity Agent API, and xAI
  for searching X with the `x_search` tool.
"""

from __future__ import annotations

from typing import Any

import httpx

from taleport.ai.providers.base import (
    DEFAULT_MAX_TOKENS,
    TIMEOUT_SECONDS,
    Completion,
    ProviderError,
    image_base64,
    image_mime,
)

_CREDIT_CODES = {
    "insufficient_quota",
    "credit_balance_exhausted",
    "organization_usage_limit_exceeded",
    "billing_hard_limit_reached",
}


def _is_credit_error(response: httpx.Response) -> bool:
    """OpenAI answers 429 both for "too many requests" and for "no prepaid credit left"."""
    try:
        error = response.json().get("error") or {}
    except ValueError:
        return False
    if isinstance(error, list):  # Gemini wraps errors in a list
        error = error[0] if error else {}
    values = {str(error.get(k, "")).lower() for k in ("code", "type", "status")}
    return bool(values & _CREDIT_CODES)


def _raise_for(response: httpx.Response, provider: str, model: str) -> None:
    if response.status_code < 400:
        return
    if response.status_code in (401, 403):
        raise ProviderError("ai.key_invalid", provider=provider)
    if response.status_code == 404:
        raise ProviderError("ai.model_not_found", model=model)
    if response.status_code == 429:
        if _is_credit_error(response):
            raise ProviderError("ai.no_credit", provider=provider)
        raise ProviderError("ai.rate_limited", provider=provider)
    raise ProviderError("ai.provider_error", provider=provider, http_status=response.status_code)


def _post(url: str, key: str, body: dict[str, Any], provider: str, model: str) -> dict[str, Any]:
    try:
        response = httpx.post(
            url, json=body, headers={"Authorization": f"Bearer {key}"}, timeout=TIMEOUT_SECONDS
        )
    except httpx.TimeoutException as exc:
        raise ProviderError("ai.timeout") from exc
    except httpx.HTTPError as exc:
        raise ProviderError("ai.network", provider=provider) from exc
    _raise_for(response, provider, model)
    return response.json()


def list_models(base_url: str, key: str, provider: str) -> list[str]:
    try:
        response = httpx.get(
            f"{base_url}/models", headers={"Authorization": f"Bearer {key}"}, timeout=15
        )
    except httpx.HTTPError as exc:
        raise ProviderError("ai.network", provider=provider) from exc
    _raise_for(response, provider, "")
    ids = [m.get("id", "") for m in response.json().get("data", [])]
    return sorted(i.removeprefix("models/") for i in ids if i)


def _user_content(user: str, images: list[bytes] | None) -> str | list[dict[str, Any]]:
    if not images:
        return user
    parts: list[dict[str, Any]] = [
        {
            "type": "image_url",
            "image_url": {"url": f"data:{image_mime(img)};base64,{image_base64(img)}"},
        }
        for img in images
    ]
    return [*parts, {"type": "text", "text": user}]


class ChatCompletionsProvider:
    paid = True
    vision = True

    def __init__(
        self,
        name: str,
        label: str,
        base_url: str,
        api_key: str,
        model: str,
        *,
        json_mode: bool = True,
        max_tokens_field: str = "max_completion_tokens",
    ) -> None:
        self.name = name
        self.label = label
        self.model = model
        self.base_url = base_url
        self._key = api_key
        self._json_mode = json_mode
        self._max_tokens_field = max_tokens_field

    def complete(
        self,
        system: str,
        user: str,
        *,
        json_output: bool,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        images: list[bytes] | None = None,
    ) -> Completion:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": _user_content(user, images)},
            ],
            self._max_tokens_field: max_tokens,
        }
        if json_output and self._json_mode:
            body["response_format"] = {"type": "json_object"}
        data = _post(f"{self.base_url}/chat/completions", self._key, body, self.label, self.model)
        choices = data.get("choices") or [{}]
        usage = data.get("usage") or {}
        return Completion(
            text=(choices[0].get("message") or {}).get("content") or "",
            model=data.get("model", self.model),
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
        )


def parse_responses_output(data: dict[str, Any]) -> tuple[str, list[str]]:
    """Text and cited URLs from a Responses-API style payload."""
    texts: list[str] = []
    citations: list[str] = []
    for item in data.get("output") or []:
        if item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if part.get("type") in ("output_text", "text"):
                texts.append(part.get("text", ""))
                for note in part.get("annotations") or []:
                    url = note.get("url")
                    if url and url not in citations:
                        citations.append(url)
    for url in data.get("citations") or []:
        if isinstance(url, str) and url not in citations:
            citations.append(url)
    return "\n".join(t for t in texts if t), citations


class ResponsesProvider:
    paid = True
    vision = False  # search agents: images are not sent

    def __init__(
        self,
        name: str,
        label: str,
        endpoint: str,
        api_key: str,
        model: str,
        *,
        tools: list[dict[str, Any]] | None = None,
    ) -> None:
        self.name = name
        self.label = label
        self.model = model
        self._endpoint = endpoint
        self._key = api_key
        self._tools = tools

    def complete(
        self,
        system: str,
        user: str,
        *,
        json_output: bool,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        images: list[bytes] | None = None,
    ) -> Completion:
        body: dict[str, Any] = {
            "model": self.model,
            "instructions": system,
            "input": user,
            "max_output_tokens": max_tokens,
        }
        if self._tools:
            body["tools"] = self._tools
        data = _post(self._endpoint, self._key, body, self.label, self.model)
        text, citations = parse_responses_output(data)
        usage = data.get("usage") or {}
        cost = (usage.get("cost") or {}).get("total_cost")
        return Completion(
            text=text,
            model=data.get("model", self.model),
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
            cost_usd=float(cost) if cost is not None else None,
            citations=citations,
        )
