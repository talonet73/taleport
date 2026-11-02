"""Google News RSS search, one query per topic edition."""

from __future__ import annotations

import feedparser

from taleport.collectors.base import CollectedItem, iso_from_struct
from taleport.collectors.http import HttpClient, ensure_ok
from taleport.collectors.text import exclusion_query, or_query
from taleport.topics.editions import EDITIONS
from taleport.topics.models import Topic

SEARCH_URL = "https://news.google.com/rss/search"
MAX_ITEMS_PER_QUERY = 40


def build_query(keywords: list[str], exclude: list[str], window_days: int) -> str:
    parts = [or_query(keywords), exclusion_query(exclude), f"when:{window_days}d"]
    return " ".join(p for p in parts if p)


class GoogleNewsCollector:
    source = "news"

    def __init__(self, http: HttpClient, window_days: int = 2) -> None:
        self._http = http
        self._window_days = window_days

    def collect(self, topic: Topic) -> list[CollectedItem]:
        items: list[CollectedItem] = []
        for code in topic.editions:
            edition = EDITIONS[code]
            keywords = topic.keywords_for(edition.language)
            if not keywords:
                continue
            response = ensure_ok(
                self._http.get(
                    SEARCH_URL,
                    params={
                        "q": build_query(keywords, topic.exclude, self._window_days),
                        "hl": edition.hl,
                        "gl": edition.gl,
                        "ceid": edition.ceid,
                    },
                )
            )
            items.extend(parse_feed(response.content, edition.language))
        return items


def parse_feed(content: bytes, language: str) -> list[CollectedItem]:
    feed = feedparser.parse(content)
    items: list[CollectedItem] = []
    for entry in feed.entries[:MAX_ITEMS_PER_QUERY]:
        link = entry.get("link")
        title = entry.get("title", "").strip()
        if not link or not title:
            continue
        publisher = (entry.get("source") or {}).get("title", "")
        if publisher and title.endswith(f" - {publisher}"):
            title = title[: -len(publisher) - 3]
        items.append(
            CollectedItem(
                source="news",
                url=link,
                title=title,
                language=language,
                publisher=publisher,
                published_at=iso_from_struct(entry.get("published_parsed")),
            )
        )
    return items
