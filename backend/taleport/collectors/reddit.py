"""Reddit via public RSS feeds only.

The anonymous JSON endpoints answer 403 and Reddit no longer self-serves API keys
(verified 2026-11), so we use the search and subreddit RSS feeds, with slow pacing.
After a block or persistent rate limit the source is switched off for the rest of the scan.
"""

from __future__ import annotations

import logging
import re

import feedparser

from taleport.collectors.base import (
    CollectedItem,
    CollectorError,
    SourceSkipped,
    iso_from_struct,
)
from taleport.collectors.http import HttpClient
from taleport.collectors.text import excerpt, or_query
from taleport.topics.models import Topic

log = logging.getLogger(__name__)

HOST = "www.reddit.com"
MIN_INTERVAL_SECONDS = 7.0
MAX_ITEMS = 25

# Reddit's feed HTML ends with "submitted by /u/name [link] [comments]": never keep user names.
_SUBMITTED_BY = re.compile(r"submitted by.*$", re.IGNORECASE | re.DOTALL)


class RedditCollector:
    source = "reddit"

    def __init__(self, http: HttpClient) -> None:
        self._http = http
        self._disabled_code: str | None = None

    def collect(self, topic: Topic) -> list[CollectedItem]:
        if self._disabled_code:
            raise SourceSkipped("reddit.unavailable")
        # Anonymous access allows about one request per minute (X-Ratelimit headers, 2026-11),
        # so each topic costs at most two: one search for all its languages and one combined
        # feed for all watched subreddits ("r/a+b+c").
        requests: list[tuple[str, dict, str | None, bool]] = []
        with_keywords = [lang for lang in topic.languages if topic.keywords_for(lang)]
        keywords = list(
            dict.fromkeys(w for lang in with_keywords for w in topic.keywords_for(lang))
        )
        if keywords:
            params = {"q": or_query(keywords), "sort": "new", "t": "week", "limit": MAX_ITEMS}
            language = with_keywords[0] if len(with_keywords) == 1 else None
            requests.append((f"https://{HOST}/search.rss", params, language, False))
        subreddits = [s.value for s in topic.sources if s.kind == "subreddit"]
        if subreddits:
            url = f"https://{HOST}/r/{'+'.join(subreddits)}/new/.rss"
            requests.append((url, {"limit": MAX_ITEMS}, None, True))

        items: list[CollectedItem] = []
        for url, params, language, watched in requests:
            try:
                items.extend(self._fetch(url, params, language=language, watched=watched))
            except CollectorError:
                # Keep what we already have; later topics are skipped via _disabled_code.
                if items:
                    log.info("Reddit stopped mid-topic %d; keeping %d items", topic.id, len(items))
                    return items
                raise
        return items

    def _fetch(
        self, url: str, params: dict, *, language: str | None, watched: bool
    ) -> list[CollectedItem]:
        try:
            response = self._http.get(url, params=params)
        except CollectorError as exc:
            if exc.code == "source.rate_limited":
                self._disabled_code = "reddit.rate_limited"
                raise CollectorError("reddit.rate_limited") from exc
            raise
        if response.status_code in (401, 403):
            self._disabled_code = "reddit.blocked"
            raise CollectorError("reddit.blocked")
        if response.status_code == 404:
            return []  # private, banned or misspelled subreddit
        if response.status_code >= 400:
            raise CollectorError("source.http", host=HOST, status=response.status_code)
        return parse_feed(response.content, language=language, watched=watched)


def parse_feed(content: bytes, *, language: str | None, watched: bool) -> list[CollectedItem]:
    feed = feedparser.parse(content)
    items: list[CollectedItem] = []
    for entry in feed.entries[:MAX_ITEMS]:
        link, title = entry.get("link"), entry.get("title", "").strip()
        # Search feeds also list matching subreddits: keep posts only.
        if not link or not title or "/comments/" not in link:
            continue
        body = ""
        if entry.get("content"):
            body = entry.content[0].get("value", "")
        body = _SUBMITTED_BY.sub("", body)
        tags = entry.get("tags") or []
        subreddit = tags[0].get("label") or tags[0].get("term") if tags else ""
        items.append(
            CollectedItem(
                source="reddit",
                url=link,
                title=title,
                excerpt=excerpt(body),
                language=language,
                publisher=subreddit or "",
                published_at=iso_from_struct(
                    entry.get("published_parsed") or entry.get("updated_parsed")
                ),
                watched=watched,
            )
        )
    return items
