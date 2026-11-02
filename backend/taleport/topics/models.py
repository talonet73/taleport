"""Topic data model and validation."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from taleport.topics.editions import EDITIONS, Language

MAX_TOPICS = 10
MAX_STYLE_EXAMPLES = 5

Platform = Literal["linkedin", "instagram", "facebook", "youtube", "tiktok"]
SourceKind = Literal["rss", "youtube_channel", "subreddit"]

_SUBREDDIT = re.compile(r"^[A-Za-z0-9_]{2,21}$")
_YT_CHANNEL_ID = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
_YT_HANDLE = re.compile(r"^@[A-Za-z0-9._-]{3,30}$")


def _clean_list(values: list[str], *, strip_hash: bool = False) -> list[str]:
    """Trim, drop empties and case-insensitive duplicates, keep order."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        value = " ".join(raw.split())
        if strip_hash:
            value = value.lstrip("#").replace(" ", "")
        if value and value.casefold() not in seen:
            seen.add(value.casefold())
            out.append(value)
    return out


class WatchedSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: SourceKind
    value: str = Field(min_length=1, max_length=500)

    @field_validator("value")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    def normalized(self) -> WatchedSource:
        """Canonical form; raises ValueError when the value is not usable for its kind."""
        value = self.value
        if self.kind == "rss":
            if not re.match(r"^https?://\S+$", value):
                raise ValueError("rss")
        elif self.kind == "subreddit":
            value = re.sub(r"^(https?://(www\.|old\.)?reddit\.com)?/?(r/)?", "", value).strip("/")
            if not _SUBREDDIT.match(value):
                raise ValueError("subreddit")
        else:
            match = re.search(r"youtube\.com/(channel/(UC[\w-]{22})|(@[\w.-]+))", value)
            if match:
                value = match.group(2) or match.group(3)
            elif not value.startswith(("@", "UC")):
                value = "@" + value
            if not (_YT_CHANNEL_ID.match(value) or _YT_HANDLE.match(value)):
                raise ValueError("youtube_channel")
        return WatchedSource(kind=self.kind, value=value)


class TopicData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    description: str = Field("", max_length=2000)
    active: bool = True
    editions: list[str] = Field(min_length=1)
    keywords: dict[Language, list[str]] = Field(default_factory=dict)
    exclude: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
    sources: list[WatchedSource] = Field(default_factory=list, max_length=30)
    audience: str = Field("", max_length=1000)
    tone: str = Field("", max_length=500)
    platforms: list[Platform] = Field(default_factory=list)
    style_examples: list[str] = Field(default_factory=list, max_length=MAX_STYLE_EXAMPLES)

    @field_validator("name", "description", "audience", "tone")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("editions")
    @classmethod
    def _known_editions(cls, value: list[str]) -> list[str]:
        unknown = [code for code in value if code not in EDITIONS]
        if unknown:
            raise ValueError(f"unknown editions: {unknown}")
        return list(dict.fromkeys(value))

    @field_validator("keywords")
    @classmethod
    def _clean_keywords(cls, value: dict[Language, list[str]]) -> dict[Language, list[str]]:
        return {lang: _clean_list(words) for lang, words in value.items() if _clean_list(words)}

    @field_validator("exclude")
    @classmethod
    def _clean_exclude(cls, value: list[str]) -> list[str]:
        return _clean_list(value)

    @field_validator("hashtags")
    @classmethod
    def _clean_hashtags(cls, value: list[str]) -> list[str]:
        return _clean_list(value, strip_hash=True)

    @field_validator("platforms")
    @classmethod
    def _unique_platforms(cls, value: list[Platform]) -> list[Platform]:
        return list(dict.fromkeys(value))

    @field_validator("style_examples")
    @classmethod
    def _clean_examples(cls, value: list[str]) -> list[str]:
        return [text.strip() for text in value if text.strip()]

    @property
    def languages(self) -> list[Language]:
        return list(dict.fromkeys(EDITIONS[code].language for code in self.editions))

    def keywords_for(self, language: Language) -> list[str]:
        return self.keywords.get(language, [])


class Topic(TopicData):
    id: int
    position: int
    created_at: str
    updated_at: str
