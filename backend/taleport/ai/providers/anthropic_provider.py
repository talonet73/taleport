"""Anthropic (Claude) through the official `anthropic` SDK."""

from __future__ import annotations

import anthropic

from taleport.ai.providers.base import (
    DEFAULT_MAX_TOKENS,
    TIMEOUT_SECONDS,
    Completion,
    ProviderError,
)

DEFAULT_MODEL = "claude-opus-5-5"
# Models that accept server-side refusal fallbacks in the "default" form: a declined request
# is re-run on Anthropic's recommended model instead of failing.
_FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    name = "anthropic"
    paid = True

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        self.model = model
        self._client = anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_SECONDS, max_retries=2)

    def complete(
        self, system: str, user: str, *, json_output: bool, max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> Completion:
        # json_output is enforced by the prompt + schema validation (no assistant prefill on
        # current models; sampling parameters are not sent).
        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        try:
            if self.model in _FALLBACK_MODELS:
                response = self._client.beta.messages.create(
                    **kwargs, betas=[_FALLBACK_BETA], fallbacks="default"
                )
            else:
                response = self._client.messages.create(**kwargs)
        except anthropic.AuthenticationError as exc:
            raise ProviderError("ai.key_invalid", provider="Anthropic") from exc
        except anthropic.PermissionDeniedError as exc:
            raise ProviderError("ai.key_invalid", provider="Anthropic") from exc
        except anthropic.NotFoundError as exc:
            raise ProviderError("ai.model_not_found", model=self.model) from exc
        except anthropic.RateLimitError as exc:
            raise ProviderError("ai.rate_limited", provider="Anthropic") from exc
        except anthropic.APITimeoutError as exc:
            raise ProviderError("ai.timeout") from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(
                "ai.provider_error", provider="Anthropic", status=exc.status_code
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError("ai.network", provider="Anthropic") from exc

        if response.stop_reason == "refusal":
            raise ProviderError("ai.refused", provider="Anthropic")
        text = "".join(block.text for block in response.content if block.type == "text")
        return Completion(
            text=text,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
