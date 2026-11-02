"""Translations for the few texts the backend shows itself (tray menu, Windows notifications)."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

_DIR = Path(__file__).resolve().parent.parent / "resources" / "i18n"
FALLBACK = "it"


@cache
def _catalog(language: str) -> dict[str, str]:
    path = _DIR / f"{language}.json"
    if not path.exists():
        path = _DIR / f"{FALLBACK}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def tr(language: str, key: str, **params: object) -> str:
    text = _catalog(language).get(key) or _catalog(FALLBACK).get(key) or key
    return text.format(**params) if params else text
