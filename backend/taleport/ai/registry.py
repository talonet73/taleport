"""Builds the provider for an AI mode from the user's settings and stored keys."""

from __future__ import annotations

from typing import Any, Literal, get_args

from taleport.ai.providers import ollama
from taleport.ai.providers.anthropic_provider import DEFAULT_MODEL as ANTHROPIC_MODEL
from taleport.ai.providers.anthropic_provider import AnthropicProvider
from taleport.ai.providers.base import LLMProvider, ProviderError
from taleport.ai.providers.openai_compat import (
    ChatCompletionsProvider,
    ResponsesProvider,
    list_models,
)
from taleport.core.secrets import SecretStore
from taleport.core.settings import AppSettings

ProviderId = Literal["ollama", "anthropic", "openai", "xai", "perplexity", "gemini"]
PROVIDER_IDS: tuple[str, ...] = get_args(ProviderId)

LABELS = {
    "ollama": "Ollama",
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "xai": "xAI",
    "perplexity": "Perplexity",
    "gemini": "Google Gemini",
}

# Defaults checked 2026-11-02 against the providers' docs; the user can change them.
DEFAULT_MODELS = {
    "ollama": "",  # first installed model
    "anthropic": ANTHROPIC_MODEL,
    "openai": "gpt-6-sol",
    "xai": "grok-4.7",
    "perplexity": "perplexity/sonar",
    "gemini": "gemini-3.8-flash",
}

BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "xai": "https://api.x.ai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
}
PERPLEXITY_AGENT_URL = "https://api.perplexity.ai/v1/agent"
XAI_RESPONSES_URL = "https://api.x.ai/v1/responses"


def model_for(provider: str, settings: AppSettings) -> str:
    return settings.ai_models.get(provider) or DEFAULT_MODELS[provider]


def _key(secrets: SecretStore, provider: str) -> str:
    key = secrets.get(provider)
    if not key:
        raise ProviderError("ai.no_key", provider=LABELS[provider])
    return key


def build_provider(provider: str, settings: AppSettings, secrets: SecretStore) -> LLMProvider:
    if provider not in PROVIDER_IDS:
        raise ProviderError("ai.unknown_provider", provider=provider)
    model = model_for(provider, settings)
    if provider == "ollama":
        if not model:
            models = ollama.list_models(settings.ollama_url)
            if not models:
                raise ProviderError("ai.ollama_no_models")
            model = models[0]
        return ollama.OllamaProvider(model, settings.ollama_url)
    key = _key(secrets, provider)
    if provider == "anthropic":
        return AnthropicProvider(key, model)
    if provider == "perplexity":
        return ResponsesProvider("perplexity", "Perplexity", PERPLEXITY_AGENT_URL, key, model)
    if provider == "gemini":
        # Gemini's OpenAI layer documents structured output via schemas, not json_object.
        return ChatCompletionsProvider(
            "gemini", LABELS["gemini"], BASE_URLS["gemini"], key, model,
            json_mode=False, max_tokens_field="max_tokens",
        )  # fmt: skip
    return ChatCompletionsProvider(provider, LABELS[provider], BASE_URLS[provider], key, model)


def build_x_search_provider(
    settings: AppSettings, secrets: SecretStore, from_date: str, to_date: str
) -> LLMProvider:
    """xAI with the `x_search` server tool (paid, uses the user's xAI key)."""
    return ResponsesProvider(
        "xai",
        "xAI",
        XAI_RESPONSES_URL,
        _key(secrets, "xai"),
        model_for("xai", settings),
        tools=[{"type": "x_search", "from_date": from_date, "to_date": to_date}],
    )


def available_models(provider: str, settings: AppSettings, secrets: SecretStore) -> list[str]:
    if provider == "ollama":
        return ollama.list_models(settings.ollama_url)
    if provider in BASE_URLS:
        return list_models(BASE_URLS[provider], _key(secrets, provider), LABELS[provider])
    return []  # Anthropic and Perplexity: the model is typed in Settings


def provider_status(provider: str, settings: AppSettings, secrets: SecretStore) -> dict[str, Any]:
    """Cheap readiness check (no paid call)."""
    status: dict[str, Any] = {
        "id": provider,
        "label": LABELS[provider],
        "model": model_for(provider, settings),
        "paid": provider != "ollama",
    }
    if provider == "ollama":
        try:
            models = ollama.list_models(settings.ollama_url, timeout=1.5)
        except ProviderError:
            status.update(
                ready=False,
                code="ai.ollama_installed_not_running"
                if ollama.installed_on_disk()
                else "ai.ollama_missing",
                models=[],
            )
            return status
        status.update(
            models=models, ready=bool(models), code=None if models else "ai.ollama_no_models"
        )
        if not status["model"] and models:
            status["model"] = models[0]
        return status
    has_key = bool(secrets.get(provider))
    status.update(ready=has_key, code=None if has_key else "ai.no_key")
    return status
