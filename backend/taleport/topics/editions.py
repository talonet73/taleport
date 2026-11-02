"""Source editions: a language + country pair, mapped to Google News locale parameters.

Verified live (2026-11): it-IT, en-US, en-GB, es-ES, es-MX. The others follow the same
documented hl/gl/ceid pattern.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Language = Literal["it", "en", "es"]
LANGUAGES: tuple[Language, ...] = ("it", "en", "es")


@dataclass(frozen=True)
class Edition:
    code: str
    language: Language
    country: str
    hl: str
    ceid: str

    @property
    def gl(self) -> str:
        return self.country


EDITIONS: dict[str, Edition] = {
    e.code: e
    for e in (
        Edition("it-IT", "it", "IT", "it", "IT:it"),
        Edition("it-CH", "it", "CH", "it", "CH:it"),
        Edition("en-US", "en", "US", "en-US", "US:en"),
        Edition("en-GB", "en", "GB", "en-GB", "GB:en"),
        Edition("en-CA", "en", "CA", "en-CA", "CA:en"),
        Edition("en-AU", "en", "AU", "en-AU", "AU:en"),
        Edition("en-IN", "en", "IN", "en-IN", "IN:en"),
        Edition("es-ES", "es", "ES", "es", "ES:es"),
        Edition("es-MX", "es", "MX", "es-419", "MX:es-419"),
        Edition("es-AR", "es", "AR", "es-419", "AR:es-419"),
        Edition("es-CO", "es", "CO", "es-419", "CO:es-419"),
        Edition("es-US", "es", "US", "es-419", "US:es-419"),
    )
}
