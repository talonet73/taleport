"""Shared types for source collectors."""

from __future__ import annotations

import calendar
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from taleport.topics.models import Topic


@dataclass
class CollectedItem:
    source: str  # news | rss | youtube | reddit | trends
    url: str
    title: str
    excerpt: str = ""
    language: str | None = None
    publisher: str = ""
    published_at: str | None = None  # ISO 8601 UTC
    metrics: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)
    # From a watched source: kept even without a keyword match.
    watched: bool = False


class CollectorError(Exception):
    """A source failed for this topic. `code` is an i18n key under `errors.`."""

    def __init__(self, code: str, **params: Any) -> None:
        super().__init__(code)
        self.code = code
        self.params = params


class SourceSkipped(Exception):
    """The source does not apply (e.g. no API key, no keywords for its languages)."""

    def __init__(self, code: str, **params: Any) -> None:
        super().__init__(code)
        self.code = code
        self.params = params


class Collector(Protocol):
    source: str

    def collect(self, topic: Topic) -> list[CollectedItem]: ...


def iso_from_struct(value: time.struct_time | None) -> str | None:
    """feedparser's *_parsed fields are UTC struct_time."""
    if not value:
        return None
    return datetime.fromtimestamp(calendar.timegm(value), UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_now() -> datetime:
    return datetime.now(UTC)
