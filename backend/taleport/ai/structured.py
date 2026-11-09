"""Asking for JSON and validating it: one corrective retry, then a clear error."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from taleport.ai.prompts import Prompt
from taleport.ai.providers.base import DEFAULT_MAX_TOKENS, Completion, LLMProvider
from taleport.core.errors import AppError

log = logging.getLogger(__name__)
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


_STRING = r'"(?:[^"\\]|\\.)*"'
# `"key": "a", "b", "c"` — a list written without brackets (small local models do this).
_BARE_LIST = re.compile(rf"(:\s*)({_STRING}(?:\s*,?\s*{_STRING}(?!\s*:))+)(?=\s*[,}}\]])")
_ADJACENT_STRINGS = re.compile(rf"({_STRING})\s+(?={_STRING})")
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def repair_json(text: str) -> str:
    """Fixes the most common mistakes of small models without touching valid JSON."""
    text = _TRAILING_COMMA.sub(r"\1", text)

    def as_list(match: re.Match[str]) -> str:
        items = _ADJACENT_STRINGS.sub(r"\1, ", match.group(2))
        return f"{match.group(1)}[{items}]"

    return _BARE_LIST.sub(as_list, text)


def extract_json(text: str) -> Any:
    """The JSON object in a model answer, tolerating code fences and chatter around it."""
    fenced = _FENCE.search(text)
    candidate = fenced.group(1) if fenced else text
    if not fenced and "```" in candidate:  # an opening fence whose closing one is missing
        candidate = candidate.split("```", 1)[1].removeprefix("json")
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found")
    body = candidate[start : end + 1]
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return json.loads(repair_json(body))


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
    images: list[bytes] | None = None,
) -> T:
    user = prompt.user
    last_error = ""
    if not getattr(provider, "paid", True):
        attempts = max(attempts, 3)  # local models are free: one more corrective try
    extra = {"images": images} if images else {}  # providers without image support never see it
    for _ in range(attempts):
        completion = provider.complete(
            prompt.system, user, json_output=True, max_tokens=max_tokens, **extra
        )
        on_completion(completion)
        try:
            return schema.model_validate(extract_json(completion.text))
        except (ValueError, ValidationError) as exc:
            last_error = _short_error(exc)
            log.warning(
                "%s/%s: invalid structured answer (%d chars): %s",
                getattr(provider, "name", "?"),
                getattr(provider, "model", "?"),
                len(completion.text),
                last_error,
            )
            user = f"{prompt.user}\n\n{prompt.retry.replace('{{error}}', last_error)}"
    raise AppError("ai.invalid_response", detail=last_error)
