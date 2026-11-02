"""Key phrase extraction with YAKE (unsupervised, multilingual, no model downloads)."""

from __future__ import annotations

import threading

import yake

from taleport.analysis.text import display_label, normalize_term

MAX_NGRAM = 2
TERMS_PER_ITEM = 6


class KeywordExtractor:
    def __init__(self) -> None:
        self._extractors: dict[str, yake.KeywordExtractor] = {}
        self._lock = threading.Lock()

    def _for(self, language: str) -> yake.KeywordExtractor:
        with self._lock:
            if language not in self._extractors:
                self._extractors[language] = yake.KeywordExtractor(
                    lan=language, n=MAX_NGRAM, top=TERMS_PER_ITEM + 4, dedupLim=0.7
                )
            return self._extractors[language]

    def extract(self, text: str, language: str) -> list[tuple[str, str]]:
        """Top key phrases as (normalized key, display label), best first."""
        if not text.strip():
            return []
        found: dict[str, str] = {}
        for phrase, _score in self._for(language).extract_keywords(text):
            key = normalize_term(phrase)
            if key and key not in found:
                found[key] = display_label(phrase)
            if len(found) == TERMS_PER_ITEM:
                break
        return list(found.items())
