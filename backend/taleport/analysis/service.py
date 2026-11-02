"""Daily statistical analysis per topic: key phrases, keyword stats, hot themes, questions.

Everything here works without AI. The AI layer (phase 4) later adds titles, summaries
and angles on top of the stored themes.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from taleport.analysis.keywords import KeywordExtractor
from taleport.analysis.questions import extract_questions
from taleport.analysis.scoring import ScoreInput, hot_score
from taleport.analysis.text import detect_language, extract_hashtags, normalize_term
from taleport.analysis.themes import Doc, build_themes
from taleport.core.errors import AppError
from taleport.db.database import Database
from taleport.generator.covered import is_covered, published_themes
from taleport.topics.models import Topic
from taleport.topics.service import TopicStore

log = logging.getLogger(__name__)

HISTORY_DAYS = 7
MAX_THEMES = 8
QUESTION_SOURCES = {"youtube", "reddit"}


def today_local() -> date:
    return datetime.now().astimezone().date()


def day_bounds_utc(day: date) -> tuple[str, str]:
    """UTC timestamps (in the DB's text format) for local midnight..midnight."""
    tz = datetime.now().astimezone().tzinfo
    start = datetime.combine(day, time(0), tz).astimezone(UTC)
    end = start + timedelta(days=1)
    fmt = "%Y-%m-%dT%H:%M:%S.000Z"
    return start.strftime(fmt), end.strftime(fmt)


def _engagement(metrics: dict[str, Any]) -> float:
    return float(metrics.get("views", 0)) / 1000 + float(metrics.get("comments", 0))


class AnalysisService:
    def __init__(self, db: Database, topics: TopicStore) -> None:
        self._db = db
        self._topics = topics
        self._extractor = KeywordExtractor()
        self._lock = threading.Lock()

    # -- pipeline ----------------------------------------------------------------------

    def analyze(self, topic_id: int, day: date | None = None) -> int:
        """(Re)compute keyword stats and themes for one topic and local day."""
        day = day or today_local()
        topic = self._topics.get(topic_id)
        start, end = day_bounds_utc(day)
        with self._lock, self._db.connect() as conn:
            rows = conn.execute(
                "SELECT i.* FROM items i JOIN item_topics t ON t.item_id = i.id "
                "WHERE t.topic_id = ? AND t.linked_at >= ? AND t.linked_at < ?",
                (topic_id, start, end),
            ).fetchall()
            items = [self._ensure_terms(conn, row) for row in rows]
            self._write_keyword_stats(conn, topic_id, day, items)
            count = self._write_themes(conn, topic, day, items)
        log.info("Analysed topic %d for %s: %d items, %d themes", topic_id, day, len(items), count)
        return count

    def _ensure_terms(self, conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["metrics"] = json.loads(item["metrics"] or "{}")
        item["extra"] = json.loads(item["extra"] or "{}")
        if item["terms"] is not None:
            # Re-check cached terms so stopword/generic list updates apply to old items too.
            item["terms"] = [
                (key, label)
                for key, label in json.loads(item["terms"])
                if normalize_term(key) == key
            ]
            item["hashtags"] = json.loads(item["hashtags"] or "[]")
            return item

        text = f"{item['title']}. {item['excerpt']}".strip()
        language = item["language"] or detect_language(text)
        terms = self._extractor.extract(text, language or "en")
        comments = " ".join(item["extra"].get("comments", []))
        hashtags = extract_hashtags(f"{text} {comments}")
        conn.execute(
            "UPDATE items SET terms = ?, hashtags = ?, language = COALESCE(language, ?) "
            "WHERE id = ?",
            (json.dumps(terms, ensure_ascii=False), json.dumps(hashtags), language, item["id"]),
        )
        item.update(terms=terms, hashtags=hashtags, language=item["language"] or language)
        return item

    @staticmethod
    def _write_keyword_stats(
        conn: sqlite3.Connection, topic_id: int, day: date, items: list[dict[str, Any]]
    ) -> None:
        counts: Counter[tuple[str, str, str, str]] = Counter()
        for item in items:
            language, source = item["language"] or "", item["source"]
            for key, _label in item["terms"]:
                counts[("keyword", key, language, source)] += 1
            for tag in item["hashtags"]:
                counts[("hashtag", tag, language, source)] += 1
        conn.execute(
            "DELETE FROM keyword_stats WHERE topic_id = ? AND day = ?", (topic_id, day.isoformat())
        )
        conn.executemany(
            "INSERT INTO keyword_stats (topic_id, day, kind, term, language, source, count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(topic_id, day.isoformat(), *key, n) for key, n in counts.items()],
        )

    def _write_themes(
        self, conn: sqlite3.Connection, topic: Topic, day: date, items: list[dict[str, Any]]
    ) -> int:
        exclude: set[str] = set()
        for words in topic.keywords.values():
            for word in words:
                if key := normalize_term(word):
                    exclude.add(key)
                    exclude.update(key.split())
        exclude.update(tag.lower() for tag in topic.hashtags)

        by_id = {item["id"]: item for item in items}
        labels: dict[str, Counter[str]] = defaultdict(Counter)
        docs: list[Doc] = []
        for item in items:
            for key, label in item["terms"]:
                labels[key][label] += 1
            docs.append(
                Doc(
                    item_id=item["id"],
                    terms=frozenset(k for k, _ in item["terms"]),
                    source=item["source"],
                    engagement=_engagement(item["metrics"]),
                )
            )
        drafts = build_themes(docs, exclude, max_themes=MAX_THEMES)

        scored = []
        for draft in drafts:
            history = self._term_history(conn, topic.id, draft.key, day)
            score, trend, details = hot_score(
                ScoreInput(
                    today=len(draft.members), previous_days=history, sources=len(draft.sources)
                )
            )
            member_items = [by_id[d.item_id] for d in draft.members]
            texts: list[str] = []
            for item in member_items:
                if item["source"] in QUESTION_SOURCES:
                    texts += [item["title"], item["excerpt"], *item["extra"].get("comments", [])]
            scored.append((score, trend, details, draft, extract_questions(texts)))
        scored.sort(key=lambda entry: -entry[0])

        # A re-analysis later the same day keeps what the AI wrote and the "X via Grok"
        # reports attached to a theme with the same key, instead of paying for them again.
        carried: dict[str, dict[str, Any]] = {}
        for row in conn.execute(
            "SELECT id, key, title, summary, angle, origin FROM themes "
            "WHERE topic_id = ? AND day = ?",
            (topic.id, day.isoformat()),
        ):
            x_items = [
                r["item_id"]
                for r in conn.execute(
                    "SELECT ti.item_id FROM theme_items ti JOIN items i ON i.id = ti.item_id "
                    "WHERE ti.theme_id = ? AND i.source = 'x_grok'",
                    (row["id"],),
                )
            ]
            carried[row["key"]] = {**dict(row), "x_items": x_items}

        conn.execute(
            "DELETE FROM themes WHERE topic_id = ? AND day = ?", (topic.id, day.isoformat())
        )
        for position, (score, trend, details, draft, questions) in enumerate(scored):
            title = labels[draft.key].most_common(1)[0][0] if labels[draft.key] else draft.key
            previous = carried.get(draft.key, {})
            ai = previous.get("origin") == "ai"
            cursor = conn.execute(
                "INSERT INTO themes (topic_id, day, key, title, summary, angle, origin, score, "
                "trend, score_details, item_count, source_count, representative_item_id, "
                "related_terms, questions, position) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    topic.id,
                    day.isoformat(),
                    draft.key,
                    previous["title"] if ai else title,
                    previous.get("summary") if ai else None,
                    previous.get("angle") if ai else None,
                    "ai" if ai else "stats",
                    score,
                    trend,
                    json.dumps(details),
                    len(draft.members),
                    len(draft.sources),
                    draft.representative().item_id,
                    json.dumps(
                        [labels[t].most_common(1)[0][0] for t in draft.related], ensure_ascii=False
                    ),
                    json.dumps(questions, ensure_ascii=False),
                    position,
                ),
            )
            member_ids = [d.item_id for d in draft.members] + previous.get("x_items", [])
            conn.executemany(
                "INSERT OR IGNORE INTO theme_items (theme_id, item_id) VALUES (?, ?)",
                [(cursor.lastrowid, item_id) for item_id in member_ids],
            )
        return len(scored)

    @staticmethod
    def _term_history(conn: sqlite3.Connection, topic_id: int, term: str, day: date) -> list[int]:
        """Item counts for `term` on the previous observed days (most recent first).

        Only days on which the topic was actually scanned count, so a topic created
        yesterday is compared with one day, not with six empty ones."""
        first = (day - timedelta(days=HISTORY_DAYS)).isoformat()
        observed = [
            r["day"]
            for r in conn.execute(
                "SELECT DISTINCT day FROM keyword_stats "
                "WHERE topic_id = ? AND day >= ? AND day < ? "
                "ORDER BY day DESC",
                (topic_id, first, day.isoformat()),
            )
        ]
        counts = {
            r["day"]: r["n"]
            for r in conn.execute(
                "SELECT day, SUM(count) AS n FROM keyword_stats "
                "WHERE topic_id = ? AND term = ? "
                "AND kind = 'keyword' AND day >= ? AND day < ? GROUP BY day",
                (topic_id, term, first, day.isoformat()),
            )
        }
        return [counts.get(d, 0) for d in observed]

    # -- read models -----------------------------------------------------------------

    def today_overview(self, day: date | None = None, themes_per_topic: int = 5) -> dict[str, Any]:
        day = day or today_local()
        start, end = day_bounds_utc(day)
        week_start = day_bounds_utc(day - timedelta(days=6))[0]
        topics = self._topics.active()
        with self._db.connect() as conn:
            items_by_topic = {
                r["topic_id"]: r["n"]
                for r in conn.execute(
                    "SELECT topic_id, COUNT(*) AS n FROM item_topics "
                    "WHERE linked_at >= ? AND linked_at < ? GROUP BY topic_id",
                    (start, end),
                )
            }
            items_today = conn.execute(
                "SELECT COUNT(DISTINCT item_id) FROM item_topics "
                "WHERE linked_at >= ? AND linked_at < ?",
                (start, end),
            ).fetchone()[0]
            posts_generated = conn.execute(
                "SELECT COUNT(*) FROM drafts WHERE created_at >= ? AND created_at < ?", (start, end)
            ).fetchone()[0]
            posts_published_week = conn.execute(
                "SELECT COUNT(*) FROM publications WHERE published_at >= ?", (week_start,)
            ).fetchone()[0]
            sections = []
            themes_today = 0
            for topic in topics:
                rows = conn.execute(
                    "SELECT * FROM themes WHERE topic_id = ? AND day = ? ORDER BY position",
                    (topic.id, day.isoformat()),
                ).fetchall()
                themes_today += len(rows)
                published = published_themes(conn, topic.id)
                sections.append(
                    {
                        "topic": {"id": topic.id, "name": topic.name},
                        "items_today": items_by_topic.get(topic.id, 0),
                        "themes": [
                            self._theme_summary(conn, row, published)
                            for row in rows[:themes_per_topic]
                        ],
                    }
                )
        return {
            "day": day.isoformat(),
            "stats": {
                "items_today": items_today,
                "themes_today": themes_today,
                "posts_generated": posts_generated,
                "posts_published_week": posts_published_week,
                "week_start": week_start,
            },
            "topics": sections,
        }

    @staticmethod
    def _theme_summary(
        conn: sqlite3.Connection,
        row: sqlite3.Row,
        published: list[tuple[str, str]] | None = None,
    ) -> dict[str, Any]:
        if published is None:
            published = published_themes(conn, row["topic_id"])
        representative = None
        if row["representative_item_id"]:
            item = conn.execute(
                "SELECT id, source, url, title, publisher FROM items WHERE id = ?",
                (row["representative_item_id"],),
            ).fetchone()
            representative = dict(item) if item else None
        sources = [
            r["source"]
            for r in conn.execute(
                "SELECT DISTINCT i.source FROM theme_items ti JOIN items i ON i.id = ti.item_id "
                "WHERE ti.theme_id = ?",
                (row["id"],),
            )
        ]
        return {
            "id": row["id"],
            "topic_id": row["topic_id"],
            "day": row["day"],
            "title": row["title"],
            "summary": row["summary"],
            "origin": row["origin"],
            "score": row["score"],
            "trend": row["trend"],
            "item_count": row["item_count"],
            "sources": sources,
            "related_terms": json.loads(row["related_terms"]),
            "question_count": len(json.loads(row["questions"])),
            "representative": representative,
            "covered": is_covered(row["key"], row["title"], published),
        }

    def theme_detail(self, theme_id: int) -> dict[str, Any]:
        with self._db.connect() as conn:
            row = conn.execute("SELECT * FROM themes WHERE id = ?", (theme_id,)).fetchone()
            if row is None:
                raise AppError("themes.not_found", status=404)
            items = [
                {**dict(r), "metrics": json.loads(r["metrics"])}
                for r in conn.execute(
                    "SELECT i.id, i.source, i.url, i.title, i.excerpt, i.language, i.publisher, "
                    "i.published_at, i.metrics FROM theme_items ti "
                    "JOIN items i ON i.id = ti.item_id "
                    "WHERE ti.theme_id = ? ORDER BY i.published_at DESC",
                    (theme_id,),
                )
            ]
            day = date.fromisoformat(row["day"])
            first = (day - timedelta(days=HISTORY_DAYS - 1)).isoformat()
            counts = {
                r["day"]: r["n"]
                for r in conn.execute(
                    "SELECT day, SUM(count) AS n FROM keyword_stats "
                    "WHERE topic_id = ? AND term = ? "
                    "AND kind = 'keyword' AND day >= ? AND day <= ? GROUP BY day",
                    (row["topic_id"], row["key"], first, row["day"]),
                )
            }
            trend7 = [
                {"day": d.isoformat(), "count": counts.get(d.isoformat(), 0)}
                for d in (day - timedelta(days=i) for i in range(HISTORY_DAYS - 1, -1, -1))
            ]
            topic = conn.execute(
                "SELECT id, name FROM topics WHERE id = ?", (row["topic_id"],)
            ).fetchone()
            summary = self._theme_summary(conn, row)
            x_reports = [
                {
                    "id": r["id"],
                    "created_at": r["first_seen_at"],
                    **{
                        k: v
                        for k, v in json.loads(r["extra"]).items()
                        if k in ("text", "via", "citations")
                    },
                }
                for r in conn.execute(
                    "SELECT i.id, i.first_seen_at, i.extra FROM theme_items ti "
                    "JOIN items i ON i.id = ti.item_id "
                    "WHERE ti.theme_id = ? AND i.source = 'x_grok' "
                    "ORDER BY i.id DESC",
                    (theme_id,),
                )
            ]
        return {
            **summary,
            "topic": dict(topic) if topic else None,
            "key": row["key"],
            "angle": row["angle"],
            "score_details": json.loads(row["score_details"]),
            "questions": json.loads(row["questions"]),
            "items": [i for i in items if i["source"] != "x_grok"],
            "x_reports": x_reports,
            "trend7": trend7,
        }
