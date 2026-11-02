"""Google Trends "Trending now" public RSS feed, one per country.

The unofficial Trends libraries (pytrends, trendspy) are unmaintained, so we use the public
daily-trends feed and keep the trending searches whose term or related headlines match the
topic's keywords or hashtags. It does not give interest-over-time for arbitrary keywords.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import quote

from taleport.collectors.base import CollectedItem, CollectorError
from taleport.collectors.http import HttpClient, ensure_ok
from taleport.collectors.text import matches_any
from taleport.topics.editions import EDITIONS
from taleport.topics.models import Topic

FEED_URL = "https://trends.google.com/trending/rss"
HT = "{https://trends.google.com/trending/rss}"


class TrendsCollector:
    source = "trends"

    def __init__(self, http: HttpClient) -> None:
        self._http = http
        self._cache: dict[str, list[dict]] = {}  # per scan: one fetch per country

    def collect(self, topic: Topic) -> list[CollectedItem]:
        items: list[CollectedItem] = []
        for code in topic.editions:
            edition = EDITIONS[code]
            keywords = topic.keywords_for(edition.language)
            hashtags = {tag.casefold() for tag in topic.hashtags}
            for trend in self._trends(edition.country):
                haystack = " ".join([trend["term"], *(n["title"] for n in trend["news"])])
                # Hashtags match the trending term only: a tag like "AI" would otherwise hit
                # the Italian preposition "ai" in headlines.
                term_as_tag = trend["term"].replace(" ", "").casefold()
                if not (matches_any(haystack, keywords) or term_as_tag in hashtags):
                    continue
                news_titles = "; ".join(n["title"] for n in trend["news"][:2])
                items.append(
                    CollectedItem(
                        source="trends",
                        url=(
                            "https://trends.google.com/trends/explore"
                            f"?q={quote(trend['term'])}&geo={edition.country}"
                        ),
                        title=trend["term"],
                        excerpt=news_titles,
                        language=edition.language,
                        publisher=f"Google Trends {edition.country}",
                        published_at=trend["published_at"],
                        metrics={"approx_traffic": trend["traffic"]},
                        extra={"news": trend["news"][:3]},
                    )
                )
        return items

    def _trends(self, country: str) -> list[dict]:
        if country not in self._cache:
            response = ensure_ok(self._http.get(FEED_URL, params={"geo": country}))
            self._cache[country] = parse_feed(response.content)
        return self._cache[country]


def parse_feed(content: bytes) -> list[dict]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise CollectorError("trends.invalid_feed") from exc
    trends: list[dict] = []
    for item in root.iter("item"):
        term = (item.findtext("title") or "").strip()
        if not term:
            continue
        published = None
        if pub := item.findtext("pubDate"):
            try:
                published = parsedate_to_datetime(pub).strftime("%Y-%m-%dT%H:%M:%SZ")
            except (TypeError, ValueError):
                published = None
        news = [
            {
                "title": (n.findtext(f"{HT}news_item_title") or "").strip(),
                "url": (n.findtext(f"{HT}news_item_url") or "").strip(),
                "source": (n.findtext(f"{HT}news_item_source") or "").strip(),
            }
            for n in item.findall(f"{HT}news_item")
        ]
        trends.append(
            {
                "term": term,
                "traffic": (item.findtext(f"{HT}approx_traffic") or "").strip(),
                "published_at": published,
                "news": [n for n in news if n["title"]],
            }
        )
    return trends
