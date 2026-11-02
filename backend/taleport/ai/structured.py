"""Asking for JSON and validating it: one corrective retry, then a clear error."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from taleport.ai.prompts import Prompt
from taleport.ai.providers.base import DEFAULT_MAX_TOKENS, Completion, LLMProvider
from taleport.core.errors import AppError

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_json(text: str) -> Any:
    """The JSON object in a model answer, tolerating code fences and chatter around it."""
    fenced = _FENCE.search(text)
    candidate = fenced.group(1) if fenced else text
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found")
    return json.loads(candidate[start : end + 1])


def _short_error(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        return f"{location}: {first['msg']}"
    return str(exc)[:200]


def parse_answer[T: BaseModel](text: str, schema: type[T]) -> T:
    """Validate a pasted answer ("Open in chat" mode)."""
    try:
        return schema.model_validate(extract_json(text))
    except (ValueError, ValidationError) as exc:
        raise AppError("ai.invalid_pasted", detail=_short_error(exc)) from exc


def run_structured[T: BaseModel](
    provider: LLMProvider,
    prompt: Prompt,
    schema: type[T],
    on_completion: Callable[[Completion], None],
    attempts: int = 2,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> T:
    user = prompt.user
    last_error = ""
    for _ in range(attempts):
        completion = provider.complete(prompt.system, user, json_output=True, max_tokens=max_tokens)
        on_completion(completion)
        try:
            return schema.model_validate(extract_json(completion.text))
        except (ValueError, ValidationError) as exc:
            last_error = _short_error(exc)
            user = f"{prompt.user}\n\n{prompt.retry.replace('{{error}}', last_error)}"
    raise AppError("ai.invalid_response", detail=last_error)
