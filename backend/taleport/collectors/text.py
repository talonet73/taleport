"""Text helpers: HTML stripping, excerpts, canonical URLs, title normalization, matching."""

from __future__ import annotations

import html
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

EXCERPT_LENGTH = 300

_TAG = re.compile(r"<[^>]+>")
_SPACES = re.compile(r"\s+")
_TRACKING_PARAMS = {
    "fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid", "igshid", "ref", "ref_src",
    "oc", "si", "feature", "cmpid", "spm",
}  # fmt: skip


def strip_html(value: str) -> str:
    return _SPACES.sub(" ", html.unescape(_TAG.sub(" ", value or ""))).strip()


def excerpt(value: str, limit: int = EXCERPT_LENGTH) -> str:
    """Short excerpt cut at a word boundary: we never store full texts."""
    text = strip_html(value)
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",.;:-") + "…"


def canonical_url(url: str) -> str:
    """Normalize a URL for duplicate detection: host, tracking params, fragments, slashes."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    for prefix in ("www.", "m.", "old.", "mobile."):
        if host.startswith(prefix):
            host = host[len(prefix) :]
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_PARAMS
    ]
    path = parts.path.rstrip("/") or "/"

    if host == "youtu.be":
        host, query, path = "youtube.com", [("v", path.strip("/"))], "/watch"
    if host == "youtube.com" and path == "/watch":
        query = [(k, v) for k, v in query if k == "v"]

    return urlunsplit(("https", host, path, urlencode(sorted(query)), ""))


def normalize_title(title: str, publisher: str = "") -> str:
    """Lowercase, accent-free, punctuation-free title, without a trailing ' - Publisher'."""
    text = title.strip()
    if publisher and text.endswith(f" - {publisher}"):
        text = text[: -len(publisher) - 3]
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w]+", " ", text)
    return _SPACES.sub(" ", text).strip()


def title_tokens(key: str) -> frozenset[str]:
    # Numbers are kept whatever their length: "model 16" and "model 17" are different stories.
    return frozenset(word for word in key.split() if len(word) > 2 or word.isdigit())


MIN_TOKENS_FOR_FUZZY = 4


def near_duplicate(a: frozenset[str], b: frozenset[str], threshold: float = 0.8) -> bool:
    """Jaccard similarity on title words; short titles never match fuzzily."""
    if len(a) < MIN_TOKENS_FOR_FUZZY or len(b) < MIN_TOKENS_FOR_FUZZY:
        return False
    return len(a & b) / len(a | b) >= threshold


def _term_pattern(term: str) -> re.Pattern[str]:
    words = [re.escape(w) for w in term.split()]
    return re.compile(r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)", re.IGNORECASE)


def matches_any(text: str, terms: list[str]) -> bool:
    return any(_term_pattern(term).search(text) for term in terms if term.strip())


def or_query(terms: list[str], *, separator: str = " OR ") -> str:
    """`"social media" OR instagram`, parenthesized when there is more than one term."""
    quoted = [f'"{t}"' if " " in t else t for t in terms]
    joined = separator.join(quoted)
    return f"({joined})" if len(quoted) > 1 and separator == " OR " else joined


def exclusion_query(terms: list[str]) -> str:
    return " ".join(f'-"{t}"' if " " in t else f"-{t}" for t in terms)
