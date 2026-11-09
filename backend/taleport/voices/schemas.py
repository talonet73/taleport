"""Tone-of-voice shapes: a saved profile and what the AI reads from reference documents."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_EXAMPLES = 6
EXAMPLE_CHARS = 600


def _clean_examples(value: object) -> object:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return value
    out: list[str] = []
    for item in value:
        text = " ".join(str(item).split()).strip().strip('«»"“”')
        if text and text not in out:
            out.append(text[:EXAMPLE_CHARS])
    return out[:MAX_EXAMPLES]


_GUIDE_KEYS = (
    "guide", "guides", "guida", "guía", "istruzioni", "instructions", "instrucciones",
    "description", "descrizione", "descripción", "tone", "tono", "rules", "regole",
)  # fmt: skip
_EXAMPLE_KEYS = ("examples", "esempi", "ejemplos", "frasi", "quotes")


class VoiceAnalysis(BaseModel):
    """The voice of one or more documents, as returned by the AI."""

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _aliases(cls, value: object) -> object:
        """Small models rename keys ("guides", "istruzioni") or wrap the object."""
        if not isinstance(value, dict):
            return value
        if "guide" not in value and isinstance(value.get("voice"), dict):
            value = value["voice"]
        value = dict(value)
        if "guide" not in value:
            for key in _GUIDE_KEYS:
                if value.get(key):
                    value["guide"] = value[key]
                    break
        if "examples" not in value:
            for key in _EXAMPLE_KEYS:
                if value.get(key):
                    value["examples"] = value[key]
                    break
        return value

    name: str = Field("", max_length=80)
    guide: str = Field(min_length=20, max_length=4000)
    examples: list[str] = Field(default_factory=list)

    @field_validator("guide", mode="before")
    @classmethod
    def _guide(cls, value: object) -> object:
        if isinstance(value, list):  # bullet points as a list
            value = "\n".join(f"- {str(v).lstrip('- ')}" for v in value if str(v).strip())
        elif isinstance(value, dict):
            value = "\n".join(f"- {k}: {v}" for k, v in value.items())
        if isinstance(value, str):
            value = value.replace("**", "")  # markdown bold: noise in a prompt
            value = re.split(r"\n\s*(?:examples|esempi|ejemplos)\s*:", value, flags=re.I)[0]
            value = value.strip()
        return value

    @field_validator("examples", mode="before")
    @classmethod
    def _examples(cls, value: object) -> object:
        return _clean_examples(value)

    @field_validator("name", mode="before")
    @classmethod
    def _name(cls, value: object) -> object:
        return (str(value or "")).strip()[:80]


class VoiceProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    guide: str = Field("", max_length=4000)
    examples: list[str] = Field(default_factory=list)
    topic_ids: list[int] = Field(default_factory=list, max_length=50)
    sources: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("empty")
        return value

    @field_validator("examples", mode="before")
    @classmethod
    def _examples(cls, value: object) -> object:
        return _clean_examples(value)
