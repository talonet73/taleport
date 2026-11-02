"""Structured post drafts as returned by the AI (validated before saving)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ScriptLine(_Lenient):
    time: str = ""
    scene: str = ""
    voiceover: str = ""


class GeneratedPost(_Lenient):
    # Plain strings on purpose: one post in an unexpected platform/language must not
    # invalidate the whole answer (and trigger a paid retry); the service drops it.
    platform: str
    language: str
    variant: int = Field(1, ge=1, le=10)
    series_index: int | None = Field(None, ge=1, le=50)
    title: str = ""
    hook: str = ""
    text: str = ""
    hashtags: list[str] = Field(default_factory=list)
    carousel: list[str] = Field(default_factory=list)
    outline: list[str] = Field(default_factory=list)
    thumbnail_idea: str = ""
    script: list[ScriptLine] = Field(default_factory=list)
    image_idea: str = ""
    image_prompt: str = ""
    sources_used: list[int] = Field(default_factory=list)

    @field_validator("platform", "language", mode="before")
    @classmethod
    def _lower(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("hashtags")
    @classmethod
    def _tags(cls, value: list[str]) -> list[str]:
        return list(
            dict.fromkeys(t.strip().lstrip("#").replace(" ", "") for t in value if t.strip())
        )

    @field_validator("sources_used", mode="before")
    @classmethod
    def _numbers(cls, value: object) -> object:
        # Models sometimes answer ["[1]", "2"]: keep the digits.
        if isinstance(value, list):
            out = []
            for v in value:
                digits = "".join(ch for ch in str(v) if ch.isdigit())
                if digits:
                    out.append(int(digits))
            return out
        return value


class GeneratedPosts(_Lenient):
    posts: list[GeneratedPost] = Field(min_length=1)
