"""People's questions, taken from YouTube comments and Reddit posts."""

from __future__ import annotations

import re

from taleport.collectors.text import normalize_title

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+|\n+")
_PREFIX = re.compile(r"^\s*(\[[^\]]{1,20}\]|\(?[a-z]{1,10}\)?:)\s*", re.IGNORECASE)
MIN_LENGTH = 15
MAX_LENGTH = 160


def extract_questions(texts: list[str], limit: int = 8) -> list[str]:
    """Distinct sentences that end with a question mark, shortest-noise first."""
    seen: set[str] = set()
    questions: list[str] = []
    for text in texts:
        for sentence in _SENTENCE_SPLIT.split(text or ""):
            sentence = _PREFIX.sub("", sentence.strip()).strip(" \"'«»“”")
            if not sentence.endswith("?") or not MIN_LENGTH <= len(sentence) <= MAX_LENGTH:
                continue
            # A real question starts like a sentence, not mid-list ("- Does it...").
            if not (sentence[0].isupper() or sentence[0] in "¿¡"):
                continue
            key = normalize_title(sentence)
            if key and key not in seen:
                seen.add(key)
                questions.append(sentence)
                if len(questions) == limit:
                    return questions
    return questions
