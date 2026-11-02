"""Versioned prompt templates in `ai/prompt_templates/{language}/{name}.md`.

A template has `# system`, `# user` and `# retry` sections and `{{variable}}` placeholders.
The first line carries the version: `<!-- version: N -->`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent / "prompt_templates"
FALLBACK_LANGUAGE = "en"
LANGUAGE_NAMES = {
    "it": {"it": "italiano", "en": "inglese", "es": "spagnolo"},
    "en": {"it": "Italian", "en": "English", "es": "Spanish"},
    "es": {"it": "italiano", "en": "inglés", "es": "español"},
}

_SECTION = re.compile(r"^# (system|user|retry)\s*$", re.MULTILINE)
_VERSION = re.compile(r"<!--\s*version:\s*(\d+)\s*-->")
_VARIABLE = re.compile(r"\{\{(\w+)\}\}")


@dataclass(frozen=True)
class Template:
    name: str
    language: str
    version: int
    system: str
    user: str
    retry: str


@dataclass(frozen=True)
class Prompt:
    name: str
    version: int
    system: str
    user: str
    retry: str  # still contains {{error}}


@cache
def load(name: str, language: str) -> Template:
    path = PROMPTS_DIR / language / f"{name}.md"
    if not path.exists():
        path = PROMPTS_DIR / FALLBACK_LANGUAGE / f"{name}.md"
    text = path.read_text(encoding="utf-8")
    version_match = _VERSION.search(text)
    parts = _SECTION.split(text)
    sections = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}
    return Template(
        name=name,
        language=language,
        version=int(version_match.group(1)) if version_match else 1,
        system=sections.get("system", ""),
        user=sections.get("user", ""),
        retry=sections.get("retry", ""),
    )


def _fill(text: str, values: dict[str, str]) -> str:
    return _VARIABLE.sub(lambda m: values.get(m.group(1), m.group(0)), text)


def render(name: str, language: str, **values: str) -> Prompt:
    template = load(name, language)
    values = {"output_language": LANGUAGE_NAMES[language][language], **values}
    return Prompt(
        name=name,
        version=template.version,
        system=_fill(template.system, values),
        user=_fill(template.user, values),
        retry=_fill(template.retry, {k: v for k, v in values.items() if k != "error"}),
    )


def language_list(codes: list[str], ui_language: str) -> str:
    return ", ".join(LANGUAGE_NAMES[ui_language].get(code, code) for code in codes)


def as_single_text(prompt: Prompt) -> str:
    """For "Open in chat": instructions and request in one message to paste."""
    return f"{prompt.system}\n\n---\n\n{prompt.user}"
