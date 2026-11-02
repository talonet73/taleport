"""The closed set of analysis functions used by Week, Keyword trends and 'Ask'.

Only these functions can be run by an 'Ask' plan: the AI never writes SQL. Every function
takes a resolved Scope and returns plain JSON-able data.

Counts come from keyword_stats: the number of collected items that mention a term on a day,
per topic, language and source. With several topics selected, an item linked to two topics
counts twice (the same as on the Trends dashboard).
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict

from taleport.ask.scope import Scope

LANGUAGES = ("it", "en", "es")
SOURCES = ("news", "rss", "youtube", "reddit", "trends", "x_grok")


def _in(column: str, values: tuple | None, params: list) -> str:
    if not values:
        return ""
    params.extend(values)
    return f" AND {column} IN ({','.join('?' * len(values))})"


def _stats_where(scope: Scope, params: list, alias: str = "") -> str:
    p = f"{alias}." if alias else ""
    params.extend([scope.start.isoformat(), scope.end.isoformat()])
    sql = f"{p}day >= ? AND {p}day <= ?"
    sql += _in(f"{p}topic_id", scope.topics, params)
    sql += _in(f"{p}language", scope.languages, params)
    sql += _in(f"{p}source", scope.sources, params)
    return sql


def total_items(conn: sqlite3.Connection, scope: Scope) -> int:
    """Collected items in scope (the denominator of the percentages)."""
    start, end = scope.utc_bounds()
    params: list = [start, end]
    sql = (
        "SELECT COUNT(*) FROM item_topics t JOIN items i ON i.id = t.item_id "
        "WHERE t.linked_at >= ? AND t.linked_at < ?"
    )
    sql += _in("t.topic_id", scope.topics, params)
    sql += _in("COALESCE(i.language, '')", scope.languages, params)
    sql += _in("i.source", scope.sources, params)
    return int(conn.execute(sql, params).fetchone()[0])


def _term_counts(
    conn: sqlite3.Connection, scope: Scope, kind: str, limit: int | None = None
) -> list[tuple[str, int]]:
    params: list = [kind]
    sql = (
        "SELECT term, SUM(count) AS n FROM keyword_stats WHERE kind = ? AND "
        + _stats_where(scope, params)
        + " GROUP BY term ORDER BY n DESC, term"
    )
    if limit:
        sql += f" LIMIT {int(limit)}"
    return [(r["term"], int(r["n"])) for r in conn.execute(sql, params)]


SUBTERM_RATIO = 0.7


def collapse_subterms(rows: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """Drop a single word that mostly appears inside a longer phrase of the same list:
    with "intelligenza artificiale" (42), "intelligenza" (23) adds nothing."""
    phrases = [(set(t.split()), n) for t, n in rows if " " in t]
    kept = []
    for term, n in rows:
        if " " not in term and any(
            term in words and pn >= SUBTERM_RATIO * n for words, pn in phrases
        ):
            continue
        kept.append((term, n))
    return kept


def _top_terms(
    conn: sqlite3.Connection, scope: Scope, kind: str, limit: int
) -> list[tuple[str, int]]:
    rows = _term_counts(conn, scope, kind, limit * 3)
    if kind == "keyword":
        rows = collapse_subterms(rows)
    return rows[:limit]


# -- functions ------------------------------------------------------------------------


def top_keywords(
    conn: sqlite3.Connection, scope: Scope, kind: str = "keyword", limit: int = 20
) -> dict:
    total = total_items(conn, scope)
    rows = [
        {"term": term, "count": n, "share": round(100 * n / total, 1) if total else 0.0}
        for term, n in _top_terms(conn, scope, kind, limit)
    ]
    return {"kind": kind, "total_items": total, "rows": rows}


def emerging_keywords(
    conn: sqlite3.Connection, scope: Scope, limit: int = 10, min_count: int = 3
) -> dict:
    """New or fast-growing terms (at least doubled), and terms that at least halved."""
    current_rows = _term_counts(conn, scope, "keyword")
    previous_scope = scope.previous()
    previous_rows = _term_counts(conn, previous_scope, "keyword")
    current, previous = dict(current_rows), dict(previous_rows)
    # Same clean-up as the top lists: "intelligenza" alone is noise next to its phrase.
    kept = {t for t, _ in collapse_subterms(current_rows)} | {
        t for t, _ in collapse_subterms(previous_rows)
    }
    emerging, declining = [], []
    # Without any data in the previous period every term would look "new": say nothing.
    terms = (set(current) | set(previous)) & kept if previous else set()
    for term in terms:
        cur, prev = current.get(term, 0), previous.get(term, 0)
        change = round(100 * (cur - prev) / prev) if prev else None
        row = {"term": term, "current": cur, "previous": prev, "change_pct": change}
        if cur >= min_count and (prev == 0 or cur >= 2 * prev):
            emerging.append(row)
        elif prev >= min_count and cur <= prev / 2:
            declining.append(row)
    emerging.sort(key=lambda r: (-(r["current"] - r["previous"]), r["term"]))
    declining.sort(key=lambda r: (-(r["previous"] - r["current"]), r["term"]))
    return {
        "previous": {
            "start": previous_scope.start.isoformat(),
            "end": previous_scope.end.isoformat(),
        },
        "has_history": bool(previous),
        "emerging": emerging[:limit],
        "declining": declining[:limit],
    }


def topic_trend(
    conn: sqlite3.Connection, scope: Scope, terms: list[str] | None = None, limit: int = 5
) -> dict:
    """Daily counts of the given terms (default: the top `limit` keywords of the period)."""
    if not terms:
        terms = [t for t, _ in _top_terms(conn, scope, "keyword", limit)]
    terms = [t.strip().lower() for t in terms if t.strip()][:8]
    days = [d.isoformat() for d in scope.days]
    series = {t: dict.fromkeys(days, 0) for t in terms}
    if terms:
        params: list = []
        sql = (
            "SELECT term, day, SUM(count) AS n FROM keyword_stats WHERE kind = 'keyword' AND "
            + _stats_where(scope, params)
            + _in("term", tuple(terms), params)
            + " GROUP BY term, day"
        )
        for r in conn.execute(sql, params):
            series[r["term"]][r["day"]] = int(r["n"])
    return {
        "days": days,
        "series": [{"term": t, "values": list(series[t].values())} for t in terms],
    }


def compare_periods(
    conn: sqlite3.Connection, scope_a: Scope, scope_b: Scope, kind: str = "keyword", limit: int = 15
) -> dict:
    a, b = dict(_term_counts(conn, scope_a, kind)), dict(_term_counts(conn, scope_b, kind))
    terms = sorted(set(a) | set(b), key=lambda t: (-(a.get(t, 0) + b.get(t, 0)), t))[:limit]
    return {
        "kind": kind,
        "period_a": {"start": scope_a.start.isoformat(), "end": scope_a.end.isoformat()},
        "period_b": {"start": scope_b.start.isoformat(), "end": scope_b.end.isoformat()},
        "rows": [{"term": t, "a": a.get(t, 0), "b": b.get(t, 0)} for t in terms],
    }


def _compare_by(
    conn: sqlite3.Connection, scope: Scope, column: str, values: tuple, limit: int
) -> dict:
    groups = []
    for value in values:
        if column == "language" and scope.languages and value not in scope.languages:
            continue
        if column == "source" and scope.sources and value not in scope.sources:
            continue
        sub = Scope(
            start=scope.start,
            end=scope.end,
            topics=scope.topics,
            languages=(value,) if column == "language" else scope.languages,
            sources=(value,) if column == "source" else scope.sources,
        )
        items = total_items(conn, sub)
        if not items:
            continue
        groups.append(
            {
                "key": value,
                "items": items,
                "top": [
                    {"term": t, "count": n} for t, n in _top_terms(conn, sub, "keyword", limit)
                ],
            }
        )
    return {"groups": groups}


def compare_languages(conn: sqlite3.Connection, scope: Scope, limit: int = 5) -> dict:
    return _compare_by(conn, scope, "language", LANGUAGES, limit)


def compare_sources(conn: sqlite3.Connection, scope: Scope, limit: int = 5) -> dict:
    return _compare_by(conn, scope, "source", SOURCES, limit)


def top_themes(conn: sqlite3.Connection, scope: Scope, limit: int = 10) -> dict:
    params: list = [scope.start.isoformat(), scope.end.isoformat()]
    sql = (
        "SELECT th.id, th.title, th.day, th.score, th.trend, th.item_count, th.origin, "
        "tp.id AS topic_id, tp.name AS topic_name FROM themes th "
        "JOIN topics tp ON tp.id = th.topic_id WHERE th.day >= ? AND th.day <= ?"
        + _in("th.topic_id", scope.topics, params)
        + f" ORDER BY th.score DESC, th.item_count DESC LIMIT {int(limit)}"
    )
    return {"rows": [dict(r) for r in conn.execute(sql, params)]}


def daily_items(conn: sqlite3.Connection, scope: Scope) -> dict:
    """Items collected per day, split by source (for the Week screen)."""
    days = [d.isoformat() for d in scope.days]
    by_source: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(days, 0))
    for day in scope.days:
        sub = Scope(
            start=day,
            end=day,
            topics=scope.topics,
            languages=scope.languages,
            sources=scope.sources,
        )
        start, end = sub.utc_bounds()
        params: list = [start, end]
        sql = (
            "SELECT i.source, COUNT(*) AS n FROM item_topics t JOIN items i ON i.id = t.item_id "
            "WHERE t.linked_at >= ? AND t.linked_at < ?"
            + _in("t.topic_id", scope.topics, params)
            + " GROUP BY i.source"
        )
        for r in conn.execute(sql, params):
            by_source[r["source"]][day.isoformat()] = int(r["n"])
    totals = [sum(src[d] for src in by_source.values()) for d in days]
    return {
        "days": days,
        "totals": totals,
        "by_source": [
            {"source": s, "values": list(v.values())} for s, v in sorted(by_source.items())
        ],
    }


def post_performance(conn: sqlite3.Connection, scope: Scope) -> dict:
    """Drafts generated and posts published per platform. Engagement metrics (likes,
    comments...) are entered by the user from phase 7 on."""
    start, end = scope.utc_bounds()
    params: list = [start, end]
    sql = (
        "SELECT platform, COUNT(*) AS generated, "
        "SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) AS published "
        "FROM drafts WHERE created_at >= ? AND created_at < ?"
        + _in("topic_id", scope.topics, params)
        + " GROUP BY platform ORDER BY generated DESC"
    )
    rows = [dict(r) for r in conn.execute(sql, params)]
    return {"rows": rows, "metrics_available": False}


FUNCTIONS = {
    "top_keywords",
    "emerging_keywords",
    "topic_trend",
    "compare_periods",
    "compare_languages",
    "compare_sources",
    "top_themes",
    "post_performance",
}
