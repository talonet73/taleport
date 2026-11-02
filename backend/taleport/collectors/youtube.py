"""YouTube Data API v3 with the user's own (free) API key.

Quota costs (units): search.list 100, videos.list 1, commentThreads.list 1,
channels.list 1, playlistItems.list 1. Watched channels use their uploads playlist,
which is far cheaper than search.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from taleport.collectors.base import CollectedItem, CollectorError, SourceSkipped, utc_now
from taleport.collectors.http import HttpClient
from taleport.collectors.quota import QuotaTracker
from taleport.collectors.text import excerpt, exclusion_query, or_query
from taleport.topics.editions import EDITIONS
from taleport.topics.models import Topic

log = logging.getLogger(__name__)

API = "https://www.googleapis.com/youtube/v3"
COST = {"search": 100, "videos": 1, "commentThreads": 1, "channels": 1, "playlistItems": 1}
SEARCH_RESULTS = 15
SEARCH_WINDOW = timedelta(days=3)
WATCHED_WINDOW = timedelta(days=7)
VIDEOS_WITH_COMMENTS = 3
COMMENTS_PER_VIDEO = 20
COMMENT_LENGTH = 300

_QUOTA_REASONS = {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"}
_KEY_REASONS = {"keyInvalid", "keyExpired", "accessNotConfigured", "forbidden", "ipRefererBlocked"}


class YouTubeCollector:
    source = "youtube"

    def __init__(
        self,
        http: HttpClient,
        quota: QuotaTracker,
        api_key: Callable[[], str | None],
        resolved_get: Callable[[int, str, str], str | None],
        resolved_set: Callable[[int, str, str, str], None],
    ) -> None:
        self._http = http
        self._quota = quota
        self._api_key = api_key
        self._resolved_get = resolved_get
        self._resolved_set = resolved_set

    # -- API access ------------------------------------------------------------------

    def _call(self, method: str, params: dict[str, Any], key: str) -> dict[str, Any]:
        self._quota.reserve(COST[method])
        response = self._http.get(f"{API}/{method}", params={**params, "key": key})
        if response.status_code < 400:
            return response.json()
        reasons = (
            {
                err.get("reason")
                for err in (response.json().get("error", {}).get("errors") or [])
                if isinstance(err, dict)
            }
            if response.headers.get("content-type", "").startswith("application/json")
            else set()
        )
        if reasons & _QUOTA_REASONS:
            self._quota.exhaust()
            raise CollectorError("youtube.quota_exhausted")
        if "commentsDisabled" in reasons:
            return {"items": []}
        if reasons & _KEY_REASONS or response.status_code in (400, 401, 403):
            raise CollectorError("youtube.key_invalid")
        raise CollectorError("source.http", host="youtube", status=response.status_code)

    # -- collection --------------------------------------------------------------------

    def collect(self, topic: Topic) -> list[CollectedItem]:
        key = self._api_key()
        if not key:
            raise SourceSkipped("youtube.no_key")

        found: dict[str, dict[str, Any]] = {}  # video id -> info
        searched: list[str] = []
        for language in topic.languages:
            keywords = topic.keywords_for(language)
            if not keywords:
                continue
            country = next(
                EDITIONS[c].country for c in topic.editions if EDITIONS[c].language == language
            )
            query = " ".join(
                p for p in (or_query(keywords, separator="|"), exclusion_query(topic.exclude)) if p
            )
            data = self._call(
                "search",
                {
                    "part": "snippet",
                    "type": "video",
                    "order": "relevance",
                    "q": query,
                    "maxResults": SEARCH_RESULTS,
                    "publishedAfter": _rfc3339(utc_now() - SEARCH_WINDOW),
                    "relevanceLanguage": language,
                    "regionCode": country,
                },
                key,
            )
            for entry in data.get("items", []):
                video_id = entry.get("id", {}).get("videoId")
                if video_id and video_id not in found:
                    found[video_id] = {"snippet": entry["snippet"], "language": language}
                    searched.append(video_id)

        for source in topic.sources:
            if source.kind == "youtube_channel":
                for video_id, snippet in self._channel_uploads(topic.id, source.value, key):
                    found.setdefault(
                        video_id, {"snippet": snippet, "language": None, "watched": True}
                    )

        if not found:
            return []
        stats = self._statistics(list(found), key)
        top = sorted(searched, key=lambda v: stats.get(v, {}).get("views", 0), reverse=True)
        comments = {v: self._comments(v, key) for v in top[:VIDEOS_WITH_COMMENTS]}

        items: list[CollectedItem] = []
        for video_id, info in found.items():
            snippet = info["snippet"]
            items.append(
                CollectedItem(
                    source="youtube",
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    title=snippet.get("title", "").strip(),
                    excerpt=excerpt(snippet.get("description", "")),
                    language=info["language"],
                    publisher=snippet.get("channelTitle", ""),
                    published_at=snippet.get("publishedAt"),
                    metrics=stats.get(video_id, {}),
                    extra={"comments": comments[video_id]} if comments.get(video_id) else {},
                    watched=info.get("watched", False),
                )
            )
        return [item for item in items if item.title]

    def _channel_uploads(self, topic_id: int, channel: str, key: str) -> list[tuple[str, dict]]:
        playlist = self._resolved_get(topic_id, "youtube_channel", channel)
        if not playlist:
            params: dict[str, Any] = {"part": "contentDetails"}
            if channel.startswith("UC"):
                params["id"] = channel
            else:
                params["forHandle"] = channel
            data = self._call("channels", params, key)
            if not data.get("items"):
                log.info("YouTube channel not found: %s", channel)
                return []
            playlist = data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
            self._resolved_set(topic_id, "youtube_channel", channel, playlist)

        data = self._call(
            "playlistItems", {"part": "snippet", "playlistId": playlist, "maxResults": 10}, key
        )
        cutoff = _rfc3339(utc_now() - WATCHED_WINDOW)
        uploads: list[tuple[str, dict]] = []
        for entry in data.get("items", []):
            snippet = entry.get("snippet", {})
            video_id = snippet.get("resourceId", {}).get("videoId")
            if video_id and snippet.get("publishedAt", "") >= cutoff:
                uploads.append((video_id, snippet))
        return uploads

    def _statistics(self, video_ids: list[str], key: str) -> dict[str, dict[str, int]]:
        stats: dict[str, dict[str, int]] = {}
        for start in range(0, len(video_ids), 50):
            chunk = video_ids[start : start + 50]
            data = self._call("videos", {"part": "statistics", "id": ",".join(chunk)}, key)
            for entry in data.get("items", []):
                s = entry.get("statistics", {})
                stats[entry["id"]] = {
                    "views": int(s.get("viewCount", 0)),
                    "likes": int(s.get("likeCount", 0)),
                    "comments": int(s.get("commentCount", 0)),
                }
        return stats

    def _comments(self, video_id: str, key: str) -> list[str]:
        """Top comments, text only: author names are never stored."""
        data = self._call(
            "commentThreads",
            {
                "part": "snippet",
                "videoId": video_id,
                "order": "relevance",
                "maxResults": COMMENTS_PER_VIDEO,
                "textFormat": "plainText",
            },
            key,
        )
        texts: list[str] = []
        for entry in data.get("items", []):
            text = entry["snippet"]["topLevelComment"]["snippet"].get("textDisplay", "")
            text = excerpt(text, COMMENT_LENGTH)
            if text:
                texts.append(text)
        return texts


def _rfc3339(value) -> str:  # type: ignore[no-untyped-def]
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")
