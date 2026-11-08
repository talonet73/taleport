"""The single internal interface every AI back end implements."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

# Generous: answers are JSON lists of themes or full topic proposals.
DEFAULT_MAX_TOKENS = 8000
TIMEOUT_SECONDS = 180.0


@dataclass
class Completion:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None  # when the provider reports the real cost
    citations: list[str] = field(default_factory=list)


class ProviderError(Exception):
    """A provider call failed. `code` is an i18n key under `errors.`."""

    def __init__(self, code: str, **params: Any) -> None:
        super().__init__(code)
        self.code = code
        self.params = params


class LLMProvider(Protocol):
    name: str
    model: str
    paid: bool  # False for local models (Ollama)
    vision: bool  # accepts images (screenshots, video frames)

    def complete(
        self,
        system: str,
        user: str,
        *,
        json_output: bool,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        images: list[bytes] | None = None,
    ) -> Completion: ...


def image_mime(data: bytes) -> str:
    """MIME type of a PNG / JPEG / WebP image from its first bytes (JPEG by default)."""
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def image_base64(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode("ascii")
