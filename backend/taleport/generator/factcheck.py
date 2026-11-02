"""Fact-check warnings: numbers, quotes and names in a draft that are not in its sources.

This is a deterministic safety net, not a verdict: it flags what a human should check
before publishing. Small counts ("3 tips") and terms the user already knows (topic
keywords, hashtags, platform names) are not flagged.
"""

from __future__ import annotations

import re
import unicodedata

MAX_WARNINGS = 12
_KNOWN = {
    "linkedin", "instagram", "facebook", "youtube", "tiktok", "reels", "reddit", "google",
    "x", "twitter", "grok", "meta", "whatsapp", "threads",
}  # fmt: skip

_NUMBER = re.compile(
    r"(?<![\w#@/.-])(\d{1,3}(?:[.,' ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
    r"\s?(%|€|\$|£|k\b|mila\b|milion[ie]\b|millones?\b|millions?\b|miliardi\b|billion\b|bn\b)?",
    re.IGNORECASE,
)
_HASHTAG = re.compile(r"(?<!\w)#\w+")
_TIMECODE = re.compile(r"\[?(?<![\w.,])\d{1,3}(?:\s*[-–]\s*\d{1,3})?\s?s\b\]?")
_QUOTE = re.compile(r"[«“\"]([^«»“”\"]{8,300})[»”\"]")
_SENTENCE = re.compile(r"(?<=[.!?…:])\s+|\n+")
_WORD = re.compile(r"[\w'’-]+", re.UNICODE)


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.replace("’", "'"))


def _digits(text: str) -> str:
    return re.sub(r"[^\d]", "", text)


def _distinctive(word: str) -> bool:
    """OpenAI, HSBC: inner capitals or all caps mark a name even at sentence start."""
    return len(word) > 2 and any(c.isupper() for c in word[1:])


def _names(text: str) -> list[str]:
    """Runs of capitalized words. A lone capitalized word is ignored unless distinctive,
    and the first word of a sentence only counts when distinctive (it is capitalized anyway)."""
    found: list[str] = []
    for sentence in _SENTENCE.split(text):
        words = _WORD.findall(sentence)
        index = 0
        while index < len(words):
            if not words[index][0].isupper():
                index += 1
                continue
            start = index
            while index < len(words) and (
                words[index][0].isupper()
                # numbers inside a name: "Il Sole 24 Ore", "Industria 4 Punto"
                or (
                    words[index].isdigit()
                    and index > start
                    and index + 1 < len(words)
                    and words[index + 1][0].isupper()
                )
            ):
                index += 1
            run = words[start:index]
            if start == 0 and not _distinctive(run[0]):
                run = run[1:]
            if len(run) >= 2 or (len(run) == 1 and _distinctive(run[0])):
                found.append(" ".join(run))
    return found


def check_facts(text: str, corpus: str, allowed: list[str] | None = None) -> list[dict[str, str]]:
    # Hashtags and video time codes ("[0-3s]", "20-40s") are not claims.
    text = _TIMECODE.sub(" ", _HASHTAG.sub(" ", text))
    names = _names(text)
    number_text = text
    for name in names:  # "24" in "Il Sole 24 Ore" belongs to the name
        number_text = number_text.replace(name, " ")
    folded_corpus = _fold(corpus)
    corpus_digits = {_digits(m.group(1)) for m in _NUMBER.finditer(corpus)}
    known = _KNOWN | {_fold(a) for a in (allowed or []) if a}
    warnings: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, value: str) -> None:
        key = (kind, _fold(value))
        if key not in seen and len(warnings) < MAX_WARNINGS:
            seen.add(key)
            warnings.append({"kind": kind, "value": value.strip()})

    for match in _NUMBER.finditer(number_text):
        raw, unit = match.group(1), match.group(2)
        digits = _digits(raw)
        if not digits or (not unit and len(digits) <= 1):
            continue  # "3 consigli", "1 domanda"
        if digits in corpus_digits or _fold(raw) in folded_corpus:
            continue
        add("number", match.group(0))

    for match in _QUOTE.finditer(text):
        quote = match.group(1)
        if len(quote.split()) >= 3 and _fold(quote) not in folded_corpus:
            add("quote", quote)

    for name in names:
        folded = _fold(name)
        if folded in known or folded in folded_corpus:
            continue
        if all(_fold(part) in known or _fold(part) in folded_corpus for part in name.split()):
            continue
        add("name", name)
    return warnings
