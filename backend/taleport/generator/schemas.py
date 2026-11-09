"""Structured post drafts as returned by the AI (validated before saving)."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore")


def _as_text(value: object) -> object:
    """Small local models sometimes answer a list or an object where a string is expected."""
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(str(_as_text(v)) for v in value if v not in (None, ""))
    if isinstance(value, dict):
        return " — ".join(str(_as_text(v)) for v in value.values() if v not in (None, ""))
    if isinstance(value, int | float):
        return str(value)
    return value


def _as_list(value: object) -> object:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return value


class ScriptLine(_Lenient):
    time: str = ""
    scene: str = ""
    voiceover: str = ""

    @model_validator(mode="before")
    @classmethod
    def _from_text(cls, value: object) -> object:
        return {"voiceover": value} if isinstance(value, str) else value

    @field_validator("time", "scene", "voiceover", mode="before")
    @classmethod
    def _text(cls, value: object) -> object:
        return _as_text(value)


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

    @field_validator(
        "title", "hook", "text", "thumbnail_idea", "image_idea", "image_prompt", mode="before"
    )
    @classmethod
    def _text(cls, value: object) -> object:
        return _as_text(value)

    @field_validator("carousel", "outline", mode="before")
    @classmethod
    def _text_list(cls, value: object) -> object:
        value = _as_list(value)
        return [_as_text(v) for v in value] if isinstance(value, list) else value

    @field_validator("script", mode="before")
    @classmethod
    def _script(cls, value: object) -> object:
        return _as_list(value)

    @field_validator("variant", "series_index", mode="before")
    @classmethod
    def _small_int(cls, value: object, info: ValidationInfo) -> object:
        # Out-of-range or textual numbers must not invalidate the whole answer.
        fallback = 1 if info.field_name == "variant" else None
        if value in (None, ""):
            return fallback
        try:
            number = int(float(str(value).strip().split()[0]))
        except (ValueError, IndexError):
            return fallback
        return min(max(number, 1), 10 if info.field_name == "variant" else 50)

    @field_validator("hashtags", mode="before")
    @classmethod
    def _tags_text(cls, value: object) -> object:
        if isinstance(value, str):  # "#a #b, #c"
            return [t for t in value.replace(",", " ").split() if t.strip("#")]
        return _as_list(value)

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

    @model_validator(mode="before")
    @classmethod
    def _wrap(cls, value: object) -> object:
        """Accept a bare list of posts, a single post, or the list under another key."""
        if isinstance(value, list):
            return {"posts": value}
        if isinstance(value, dict) and "posts" not in value:
            if "platform" in value and "text" in value:
                return {"posts": [value]}
            lists = [
                v for v in value.values() if isinstance(v, list) and v and isinstance(v[0], dict)
            ]
            if len(lists) == 1:
                return {"posts": lists[0]}
        return value
