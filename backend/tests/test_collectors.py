"""Collectors against recorded responses (tests/fixtures) and mocked HTTP."""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import respx

from taleport.collectors.base import CollectorError, SourceSkipped
from taleport.collectors.google_news import GoogleNewsCollector, build_query
from taleport.collectors.http import HttpClient
from taleport.collectors.quota import QuotaTracker
from taleport.collectors.reddit import RedditCollector
from taleport.collectors.rss import RssCollector
from taleport.collectors.trends import TrendsCollector
from taleport.collectors.youtube import YouTubeCollector
from taleport.db.database import Database
from taleport.topics.service import TopicStore
from tests.conftest import FIXTURES, topic_payload


@pytest.fixture
def http() -> HttpClient:
    return HttpClient(sleep=lambda _s: None, backoff=0)


@pytest.fixture
def store(db: Database) -> TopicStore:
    return TopicStore(db)


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


# -- HTTP client ---------------------------------------------------------------------


@respx.mock
def test_http_retries_server_errors_then_succeeds(http: HttpClient) -> None:
    route = respx.get("https://x.test/feed").mock(
        side_effect=[httpx.Response(503), httpx.Response(429), httpx.Response(200, text="ok")]
    )
    assert http.get("https://x.test/feed").text == "ok"
    assert route.call_count == 3


@respx.mock
def test_http_gives_up_with_a_coded_error(http: HttpClient) -> None:
    respx.get("https://x.test/feed").mock(return_value=httpx.Response(429))
    with pytest.raises(CollectorError) as info:
        http.get("https://x.test/feed")
    assert info.value.code == "source.rate_limited"

    respx.get("https://y.test/").mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(CollectorError) as info:
        http.get("https://y.test/")
    assert info.value.code == "source.network"


def test_http_paces_requests_per_host() -> None:
    waits: list[float] = []
    client = HttpClient(
        sleep=waits.append,
        min_interval={"slow.test": 5.0},
        transport=httpx.MockTransport(lambda _r: httpx.Response(200)),
    )
    client.get("https://slow.test/a")
    client.get("https://slow.test/b")
    client.get("https://fast.test/c")
    assert len(waits) == 1 and 4.0 < waits[0] <= 5.0


def test_http_waits_for_rate_limit_window_when_budget_is_used_up() -> None:
    waits: list[float] = []
    headers = {"X-Ratelimit-Remaining": "0.0", "X-Ratelimit-Reset": "12"}
    client = HttpClient(
        sleep=waits.append,
        transport=httpx.MockTransport(lambda _r: httpx.Response(200, headers=headers)),
    )
    client.get("https://limited.test/a")
    assert waits == []
    client.get("https://limited.test/b")
    assert len(waits) == 1 and 11.0 < waits[0] <= 12.0


@respx.mock
def test_http_uses_ratelimit_reset_on_429(http: HttpClient) -> None:
    waits: list[float] = []
    client = HttpClient(sleep=waits.append, backoff=0)
    respx.get("https://r.test/").mock(
        side_effect=[httpx.Response(429, headers={"X-Ratelimit-Reset": "9"}), httpx.Response(200)]
    )
    assert client.get("https://r.test/").status_code == 200
    assert 9.0 in [round(w) for w in waits]


# -- Google News ---------------------------------------------------------------------


def test_google_news_query_syntax() -> None:
    assert (
        build_query(["social media", "ads"], ["crypto"], 2)
        == '("social media" OR ads) -crypto when:2d'
    )


@respx.mock
def test_google_news_queries_each_edition(http: HttpClient, store: TopicStore) -> None:
    route = respx.get("https://news.google.com/rss/search").mock(
        return_value=httpx.Response(200, content=fixture("google_news_it.xml"))
    )
    topic = store.create(topic_payload(editions=["it-IT", "en-US", "es-ES"]))  # no es keywords
    items = GoogleNewsCollector(http).collect(topic)

    assert route.call_count == 2
    params = [parse_qs(urlsplit(str(c.request.url)).query) for c in route.calls]
    assert params[0]["ceid"] == ["IT:it"] and params[1]["ceid"] == ["US:en"]
    assert "-crypto" in params[0]["q"][0]
    assert len(items) == 12
    first = items[0]
    assert first.source == "news" and first.language == "it" and first.publisher
    assert not first.title.endswith(f" - {first.publisher}")
    assert first.published_at and first.published_at.endswith("Z")


# -- Reddit --------------------------------------------------------------------------


@respx.mock
def test_reddit_search_and_watched_subreddits(http: HttpClient, store: TopicStore) -> None:
    respx.get("https://www.reddit.com/search.rss").mock(
        return_value=httpx.Response(200, content=fixture("reddit_search.xml"))
    )
    sub = respx.get("https://www.reddit.com/r/socialmedia/new/.rss").mock(
        return_value=httpx.Response(200, content=fixture("reddit_search.xml"))
    )
    topic = store.create(
        topic_payload(editions=["en-US"], sources=[{"kind": "subreddit", "value": "socialmedia"}])
    )
    items = RedditCollector(http).collect(topic)

    assert sub.called
    assert items and len(items) % 2 == 0  # same fixture for search and subreddit
    assert [i.watched for i in items].count(True) == len(items) // 2
    for item in items:
        assert "/comments/" in item.url  # subreddit listings are dropped
        assert "submitted by" not in item.excerpt and "/u/" not in item.excerpt
        assert item.publisher.startswith("r/")


@respx.mock
def test_reddit_block_disables_source_for_the_scan(http: HttpClient, store: TopicStore) -> None:
    route = respx.get("https://www.reddit.com/search.rss").mock(return_value=httpx.Response(403))
    collector = RedditCollector(http)
    topic = store.create(topic_payload(editions=["en-US"]))
    with pytest.raises(CollectorError) as info:
        collector.collect(topic)
    assert info.value.code == "reddit.blocked"
    with pytest.raises(SourceSkipped):
        collector.collect(topic)
    assert route.call_count == 1


@respx.mock
def test_reddit_keeps_items_when_a_later_request_is_limited(
    http: HttpClient, store: TopicStore
) -> None:
    search = respx.get("https://www.reddit.com/search.rss").mock(
        return_value=httpx.Response(200, content=fixture("reddit_search.xml"))
    )
    respx.get("https://www.reddit.com/r/aa+bb/new/.rss").mock(return_value=httpx.Response(429))
    collector = RedditCollector(http)
    topic = store.create(
        topic_payload(
            sources=[{"kind": "subreddit", "value": "aa"}, {"kind": "subreddit", "value": "bb"}]
        )
    )
    items = collector.collect(topic)
    # it + en keywords go in a single search request
    assert search.call_count == 1
    query = parse_qs(urlsplit(str(search.calls[0].request.url)).query)["q"][0]
    assert "intelligenza artificiale" in query and "artificial intelligence" in query
    assert items  # results of the first search survive
    with pytest.raises(SourceSkipped):
        collector.collect(topic)  # and Reddit is paused for the rest of the scan


# -- Trends --------------------------------------------------------------------------


@respx.mock
def test_trends_keeps_matching_terms_and_fetches_once_per_country(
    http: HttpClient, store: TopicStore
) -> None:
    route = respx.get("https://trends.google.com/trending/rss").mock(
        return_value=httpx.Response(200, content=fixture("trends_it.xml"))
    )
    collector = TrendsCollector(http)
    matching = store.create(
        topic_payload(name="Space", editions=["it-IT"], keywords={"it": ["nasa"]})
    )
    other = store.create(topic_payload(name="Food", editions=["it-IT"], keywords={"it": ["pizza"]}))

    items = collector.collect(matching)
    assert [i.title for i in items] == ["nasa"]
    assert items[0].metrics["approx_traffic"] and items[0].extra["news"]
    assert collector.collect(other) == []
    assert route.call_count == 1
    # "#AI" must not match the Italian preposition "ai" inside headlines.
    tagged = store.create(
        topic_payload(
            name="Tags", editions=["it-IT"], keywords={"it": ["pizza"]}, hashtags=["ai", "NASA"]
        )
    )
    assert [i.title for i in collector.collect(tagged)] == ["nasa"]


# -- RSS -----------------------------------------------------------------------------


@respx.mock
def test_rss_watched_feed(http: HttpClient, store: TopicStore) -> None:
    respx.get("https://example.com/feed.xml").mock(
        return_value=httpx.Response(200, content=fixture("google_news_it.xml"))
    )
    respx.get("https://broken.example.com/feed").mock(return_value=httpx.Response(404))
    topic = store.create(
        topic_payload(
            sources=[
                {"kind": "rss", "value": "https://example.com/feed.xml"},
                {"kind": "rss", "value": "https://broken.example.com/feed"},
            ]
        )
    )
    items = RssCollector(http).collect(topic)
    assert len(items) == 6 and all(i.watched and i.source == "rss" for i in items)


# -- YouTube -------------------------------------------------------------------------


def _video_search() -> dict:
    return {
        "items": [
            {
                "id": {"videoId": vid},
                "snippet": {
                    "title": f"Video {vid}",
                    "description": "desc",
                    "channelTitle": "Chan",
                    "publishedAt": "2026-11-01T10:00:00Z",
                },
            }
            for vid in ("v1", "v2")
        ]
    }


@respx.mock
def test_youtube_collects_stats_and_comments_within_quota(
    db: Database, http: HttpClient, store: TopicStore
) -> None:
    quota = QuotaTracker(db)
    respx.get("https://www.googleapis.com/youtube/v3/search").mock(
        return_value=httpx.Response(200, json=_video_search())
    )
    respx.get("https://www.googleapis.com/youtube/v3/videos").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"id": "v1", "statistics": {"viewCount": "10", "commentCount": "2"}},
                    {"id": "v2", "statistics": {"viewCount": "500"}},
                ]
            },
        )
    )
    respx.get("https://www.googleapis.com/youtube/v3/commentThreads").mock(
        return_value=httpx.Response(
            200,
            json={"items": [{"snippet": {"topLevelComment": {"snippet": {
                "textDisplay": "Come si usa per Instagram?", "authorDisplayName": "Mario"}}}}]},
        )
    )  # fmt: skip
    topic = store.create(topic_payload(editions=["it-IT"]))
    collector = YouTubeCollector(
        http, quota, lambda: "KEY", store.source_resolved, store.set_source_resolved
    )
    items = collector.collect(topic)

    assert {i.url for i in items} == {
        "https://www.youtube.com/watch?v=v1",
        "https://www.youtube.com/watch?v=v2",
    }
    v2 = next(i for i in items if i.url.endswith("v2"))
    assert v2.metrics["views"] == 500
    assert v2.extra["comments"] == ["Come si usa per Instagram?"]
    assert "Mario" not in str([i.extra for i in items])
    assert quota.used() == 100 + 1 + 2  # search + videos + 2 comment threads


def test_youtube_without_key_is_skipped(db: Database, http: HttpClient, store: TopicStore) -> None:
    topic = store.create(topic_payload())
    collector = YouTubeCollector(
        http, QuotaTracker(db), lambda: None, store.source_resolved, store.set_source_resolved
    )
    with pytest.raises(SourceSkipped) as info:
        collector.collect(topic)
    assert info.value.code == "youtube.no_key"


@respx.mock
def test_youtube_stops_when_quota_is_used_up(
    db: Database, http: HttpClient, store: TopicStore
) -> None:
    quota = QuotaTracker(db, limit=150)
    quota.reserve(100)
    route = respx.get("https://www.googleapis.com/youtube/v3/search")
    topic = store.create(topic_payload(editions=["it-IT"]))
    collector = YouTubeCollector(
        http, quota, lambda: "KEY", store.source_resolved, store.set_source_resolved
    )
    with pytest.raises(CollectorError) as info:
        collector.collect(topic)
    assert info.value.code == "youtube.quota_exhausted"
    assert not route.called


@respx.mock
def test_youtube_api_quota_error_is_reported(
    db: Database, http: HttpClient, store: TopicStore
) -> None:
    quota = QuotaTracker(db)
    respx.get("https://www.googleapis.com/youtube/v3/search").mock(
        return_value=httpx.Response(
            403, json={"error": {"code": 403, "errors": [{"reason": "quotaExceeded"}]}}
        )
    )
    topic = store.create(topic_payload(editions=["it-IT"]))
    collector = YouTubeCollector(
        http, quota, lambda: "KEY", store.source_resolved, store.set_source_resolved
    )
    with pytest.raises(CollectorError) as info:
        collector.collect(topic)
    assert info.value.code == "youtube.quota_exhausted"
    assert quota.status()["remaining"] == 0
