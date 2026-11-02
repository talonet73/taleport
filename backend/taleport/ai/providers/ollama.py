"""Ollama: local, free models (http://localhost:11434 by default)."""

from __future__ import annotations

import os
from pathlib import Path

import httpx

from taleport.ai.providers.base import (
    DEFAULT_MAX_TOKENS,
    TIMEOUT_SECONDS,
    Completion,
    ProviderError,
)

DEFAULT_URL = "http://localhost:11434"


def installed_on_disk() -> bool:
    """Default per-user install location of Ollama for Windows."""
    local = os.environ.get("LOCALAPPDATA", "")
    return bool(local) and (Path(local) / "Programs" / "Ollama" / "ollama.exe").exists()


def list_models(base_url: str, timeout: float = 3.0) -> list[str]:
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ProviderError("ai.ollama_unreachable", url=base_url) from exc
    return [m["name"] for m in response.json().get("models", []) if m.get("name")]


class OllamaProvider:
    name = "ollama"
    paid = False

    def __init__(self, model: str, base_url: str = DEFAULT_URL) -> None:
        self.model = model
        self._url = base_url.rstrip("/")

    def complete(
        self, system: str, user: str, *, json_output: bool, max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> Completion:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "options": {"num_predict": max_tokens, "num_ctx": 16384},
        }
        if json_output:
            body["format"] = "json"
        try:
            response = httpx.post(f"{self._url}/api/chat", json=body, timeout=TIMEOUT_SECONDS * 2)
        except httpx.TimeoutException as exc:
            raise ProviderError("ai.timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("ai.ollama_unreachable", url=self._url) from exc
        if response.status_code == 404:
            raise ProviderError("ai.model_not_found", model=self.model)
        if response.status_code >= 400:
            raise ProviderError("ai.provider_error", provider="Ollama", status=response.status_code)
        data = response.json()
        return Completion(
            text=data.get("message", {}).get("content", ""),
            model=self.model,
            input_tokens=int(data.get("prompt_eval_count", 0)),
            output_tokens=int(data.get("eval_count", 0)),
            cost_usd=0.0,
        )
