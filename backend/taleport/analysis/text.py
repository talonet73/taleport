"""Language detection, term normalization and hashtag extraction (IT/EN/ES, offline)."""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

_STOPWORDS_DIR = Path(__file__).resolve().parent.parent / "resources" / "stopwords"
LANGUAGES = ("it", "en", "es")

_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?", re.UNICODE)
_HASHTAG = re.compile(r"(?<![\w#])#([^\W_][\w]{1,39})", re.UNICODE)
# Italian elisions such as l', dell', sull', un', quest' in front of a word.
_ELISION = re.compile(r"^[^\W\d_]{1,6}'(?=[^\W\d_])", re.UNICODE)
_EDGE_PUNCT = re.compile(r"^[\W_]+|[\W_]+$", re.UNICODE)


@cache
def stopwords(language: str) -> frozenset[str]:
    path = _STOPWORDS_DIR / f"{language}.txt"
    if not path.exists():
        return frozenset()
    return frozenset(w.strip() for w in path.read_text(encoding="utf-8").splitlines() if w.strip())


@cache
def all_stopwords() -> frozenset[str]:
    return frozenset().union(*(stopwords(lang) for lang in LANGUAGES))


@cache
def generic_words() -> frozenset[str]:
    lines = (_STOPWORDS_DIR / "generic.txt").read_text(encoding="utf-8").splitlines()
    return frozenset(w.strip() for w in lines if w.strip() and not w.startswith("#"))


def _clean(text: str) -> str:
    return text.replace("’", "'").replace("‘", "'")


def detect_language(text: str) -> str | None:
    """Most likely of it/en/es by stopword hits; None when the evidence is too thin."""
    words = [w.lower() for w in _WORD.findall(_clean(text))]
    if len(words) < 3:
        return None
    scores = {lang: sum(w in stopwords(lang) for w in words) for lang in LANGUAGES}
    best = max(scores, key=lambda lang: scores[lang])
    ranked = sorted(scores.values(), reverse=True)
    if ranked[0] < 2 or ranked[0] == ranked[1]:
        return None
    return best


def normalize_term(raw: str) -> str | None:
    """Lowercase key phrase without elisions or edge stopwords; None when not meaningful."""
    words: list[str] = []
    for word in _clean(raw).lower().split():
        word = _EDGE_PUNCT.sub("", _ELISION.sub("", word))
        if word:
            words.append(word)
    stops = all_stopwords()
    while words and words[0] in stops:
        words.pop(0)
    while words and words[-1] in stops:
        words.pop()
    if not words:
        return None
    term = " ".join(words)
    if len(term) < 3 or term.replace(" ", "").isdigit():
        return None
    if len(words) == 1 and term in generic_words():
        return None
    return term


def display_label(surface: str) -> str:
    """Readable label from an extracted surface form (keeps acronyms and proper nouns)."""
    words = [_EDGE_PUNCT.sub("", _ELISION.sub("", w)) for w in _clean(surface).split()]
    label = " ".join(w for w in words if w)
    return label[:1].upper() + label[1:] if label else surface


def extract_hashtags(text: str) -> list[str]:
    return list(dict.fromkeys(tag.lower() for tag in _HASHTAG.findall(text)))
