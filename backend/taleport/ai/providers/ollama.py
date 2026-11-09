"""Ollama: local, free models (http://localhost:11434 by default)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import httpx

from taleport.ai.providers.base import (
    DEFAULT_MAX_TOKENS,
    TIMEOUT_SECONDS,
    Completion,
    ProviderError,
    image_base64,
)

DEFAULT_URL = "http://localhost:11434"

log = logging.getLogger(__name__)


def _error_text(response: httpx.Response) -> str:
    try:
        return str(response.json().get("error", ""))[:300]
    except ValueError:
        return response.text[:300]


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
    vision = True  # only vision models (llava, gemma3, qwen2.5vl...) can read the images

    def __init__(self, model: str, base_url: str = DEFAULT_URL) -> None:
        self.model = model
        self._url = base_url.rstrip("/")

    def _post(self, body: dict) -> httpx.Response:
        try:
            return httpx.post(f"{self._url}/api/chat", json=body, timeout=TIMEOUT_SECONDS * 2)
        except httpx.TimeoutException as exc:
            raise ProviderError("ai.timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("ai.ollama_unreachable", url=self._url) from exc

    def complete(
        self,
        system: str,
        user: str,
        *,
        json_output: bool,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        images: list[bytes] | None = None,
    ) -> Completion:
        message: dict = {"role": "user", "content": user}
        if images:
            message["images"] = [image_base64(img) for img in images]
        options: dict = {"num_predict": max_tokens, "num_ctx": 16384}
        if json_output:
            options["temperature"] = 0.4  # fewer malformed answers from small local models
        body: dict = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, message],
            "stream": False,
            "options": options,
        }
        if json_output:
            body["format"] = "json"
        response = self._post(body)
        if response.status_code >= 500 and json_output and not images:
            # Ollama sometimes stops mid-answer while forcing JSON: the prompt already asks
            # for JSON, so one more try without the grammar usually works.
            log.warning(
                "Ollama %s: %s; retrying without JSON mode",
                response.status_code,
                _error_text(response),
            )
            body.pop("format", None)
            response = self._post(body)
        if response.status_code == 404:
            raise ProviderError("ai.model_not_found", model=self.model)
        if response.status_code >= 400:
            detail = _error_text(response)
            log.warning("Ollama %s: %s", response.status_code, detail)
            if images:
                raise ProviderError("ai.no_vision", model=self.model)
            if "memory" in detail.lower():
                raise ProviderError("ai.ollama_memory", model=self.model)
            raise ProviderError(
                "ai.provider_error", provider="Ollama", http_status=response.status_code
            )
        data = response.json()
        return Completion(
            text=data.get("message", {}).get("content", ""),
            model=self.model,
            input_tokens=int(data.get("prompt_eval_count", 0)),
            output_tokens=int(data.get("eval_count", 0)),
            cost_usd=0.0,
        )
