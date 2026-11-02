"""User-provided RSS/Atom feeds (watched sources)."""

from __future__ import annotations

from datetime import timedelta

import feedparser

from taleport.collectors.base import CollectedItem, CollectorError, iso_from_struct, utc_now
from taleport.collectors.http import HttpClient, ensure_ok
from taleport.collectors.text import excerpt
from taleport.topics.models import Topic

MAX_ITEMS_PER_FEED = 30
MAX_AGE = timedelta(days=7)


class RssCollector:
    source = "rss"

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def collect(self, topic: Topic) -> list[CollectedItem]:
        feeds = [s.value for s in topic.sources if s.kind == "rss"]
        items: list[CollectedItem] = []
        failures: list[str] = []
        for url in feeds:
            try:
                response = ensure_ok(self._http.get(url))
                items.extend(parse_feed(response.content))
            except CollectorError:
                failures.append(url)
        if failures and not items:
            raise CollectorError("rss.feeds_failed", count=len(failures), url=failures[0])
        return items


def parse_feed(content: bytes) -> list[CollectedItem]:
    feed = feedparser.parse(content)
    if feed.bozo and not feed.entries:
        raise CollectorError("rss.invalid_feed")
    publisher = feed.feed.get("title", "")
    cutoff = (utc_now() - MAX_AGE).strftime("%Y-%m-%dT%H:%M:%SZ")
    items: list[CollectedItem] = []
    for entry in feed.entries[:MAX_ITEMS_PER_FEED]:
        link, title = entry.get("link"), entry.get("title", "").strip()
        if not link or not title:
            continue
        published = iso_from_struct(entry.get("published_parsed") or entry.get("updated_parsed"))
        if published and published < cutoff:
            continue
        items.append(
            CollectedItem(
                source="rss",
                url=link,
                title=title,
                excerpt=excerpt(entry.get("summary", "")),
                publisher=publisher,
                published_at=published,
                watched=True,
            )
        )
    return items
