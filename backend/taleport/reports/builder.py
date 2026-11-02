"""Report content: which data goes in each report and in which order.

Every section reads the same closed analysis functions as the dashboards and 'Ask'
(`ask.functions`), so a PDF always matches what the app shows. The summary uses the
theme summaries the AI already wrote (when present): building a report never calls an AI.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import date
from typing import Any

from taleport.ask import functions as fn
from taleport.ask.scope import Filters, Period, Scope
from taleport.core.i18n import tr
from taleport.reports.model import Report, Section
from taleport.results.service import ResultsService

SECTIONS = ("summary", "themes", "keywords", "changes", "trend", "compare", "posts", "results")
MAX_THEMES = 10
MAX_LINKS_PER_THEME = 3
MAX_PUBLISHED = 25

T = Callable[..., str]


def translator(language: str) -> T:
    return lambda key, **params: tr(language, f"report.{key}", **params)


def format_day(day: date | str, language: str) -> str:
    day = date.fromisoformat(day) if isinstance(day, str) else day
    months = tr(language, "report.months").split(",")
    return f"{day.day} {months[day.month - 1]} {day.year}"


def short_day(day: date | str, language: str) -> str:
    """ "2 nov" for chart axes: full month names collide when days are close together."""
    day = date.fromisoformat(day) if isinstance(day, str) else day
    months = tr(language, "report.months_short").split(",")
    return f"{day.day} {months[day.month - 1]}"


def format_period(start: date | str, end: date | str, language: str) -> str:
    if str(start) == str(end):
        return format_day(start, language)
    return f"{format_day(start, language)} – {format_day(end, language)}"


def _number(value: float | int | None, language: str) -> str:
    if value is None:
        return "–"
    text = (
        f"{value:,.1f}" if isinstance(value, float) and not value.is_integer() else f"{value:,.0f}"
    )
    if language in ("it", "es"):  # 1.234,5
        text = text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return text


class ReportBuilder:
    def __init__(self, conn: sqlite3.Connection, language: str, results: ResultsService) -> None:
        self.conn = conn
        self.language = language
        self.t = translator(language)
        self._results = results
        self._topic_names = {
            r["id"]: r["name"] for r in conn.execute("SELECT id, name FROM topics")
        }

    def n(self, value: float | int | None) -> str:
        return _number(value, self.language)

    # -- report kinds --------------------------------------------------------------------

    def daily(self, day: date) -> Report:
        scope = Scope.build(Period(preset="custom", start=day, end=day), None, day)
        report = Report(
            "daily", self.t("title.daily"), format_day(day, self.language), self.language
        )
        for name in ("summary", "themes", "keywords", "posts"):
            getattr(self, f"_section_{name}")(report, scope)
        return report

    def weekly(self, today: date) -> Report:
        scope = Scope.build(Period(preset="last_7_days"), None, today)
        report = Report("weekly", self.t("title.weekly"), self._period(scope), self.language)
        self._section_summary(report, scope, daily_chart=True)
        for name in ("themes", "keywords", "changes", "trend", "posts", "results"):
            getattr(self, f"_section_{name}")(report, scope)
        return report

    def trends(self, period: Period, filters: Filters | None, today: date | None = None) -> Report:
        scope = Scope.build(period, filters, today)
        report = Report("trends", self.t("title.trends"), self._period(scope), self.language)
        for name in ("keywords", "changes", "trend", "compare"):
            getattr(self, f"_section_{name}")(report, scope)
        return report

    def custom(
        self,
        title: str,
        period: Period,
        filters: Filters | None,
        sections: list[str],
        today: date | None = None,
    ) -> Report:
        scope = Scope.build(period, filters, today)
        report = Report(
            "custom", title or self.t("title.custom"), self._period(scope), self.language
        )
        for name in SECTIONS:  # fixed order, whatever order they were ticked in
            if name in sections:
                getattr(self, f"_section_{name}")(report, scope)
        return report

    def ask(self, question: str, result: dict[str, Any]) -> Report:
        """A report from an 'Ask' answer: one section per step of the validated plan."""
        steps = result["steps"]
        scopes = [
            scope
            for s in steps
            for scope in (
                [s["scope"]["period_a"], s["scope"]["period_b"]]
                if "period_a" in s["scope"]
                else [s["scope"]]
            )
        ]
        start = min(s["start"] for s in scopes)
        end = max(s["end"] for s in scopes)
        title = result.get("title") or question or self.t("title.ask")
        report = Report("ask", title, format_period(start, end, self.language), self.language)
        if question:
            report.section(self.t("ask.question")).add("text", text=question)
        for step in steps:
            section = report.section(self.t(f"functions.{step['function']}"))
            scope = step["scope"]
            if "period_a" in scope:
                section.add(
                    "note",
                    text=self.t(
                        "ask.periods",
                        a=format_period(
                            scope["period_a"]["start"], scope["period_a"]["end"], self.language
                        ),
                        b=format_period(
                            scope["period_b"]["start"], scope["period_b"]["end"], self.language
                        ),
                    ),
                )
            else:
                section.add("note", text=self._scope_note(scope))
            self._render_step(section, step["function"], step["result"])
        return report

    # -- helpers -------------------------------------------------------------------------

    def _period(self, scope: Scope) -> str:
        return format_period(scope.start, scope.end, self.language)

    def _scope_note(self, scope: dict[str, Any]) -> str:
        parts = [format_period(scope["start"], scope["end"], self.language)]
        if scope.get("topics"):
            parts.append(", ".join(self._topic_names.get(t, str(t)) for t in scope["topics"]))
        if scope.get("languages"):
            parts.append(
                ", ".join(tr(self.language, f"report.language.{x}") for x in scope["languages"])
            )
        if scope.get("sources"):
            parts.append(", ".join(tr(self.language, f"source.{x}") for x in scope["sources"]))
        return " · ".join(parts)

    def _render_step(self, section: Section, function: str, result: dict[str, Any]) -> None:
        match function:
            case "top_keywords":
                self._keywords_block(section, result)
            case "emerging_keywords":
                self._changes_blocks(section, result)
            case "topic_trend":
                self._trend_blocks(section, result)
            case "compare_periods":
                t = self.t
                section.add(
                    "table",
                    header=[t("col.term"), t("col.period_a"), t("col.period_b")],
                    rows=[[r["term"], self.n(r["a"]), self.n(r["b"])] for r in result["rows"]],
                    align=["left", "right", "right"],
                )
            case "compare_languages" | "compare_sources":
                self._groups_blocks(
                    section, result, "language" if function.endswith("languages") else "source"
                )
            case "top_themes":
                self._themes_blocks(section, result["rows"], with_links=False)
            case "post_performance":
                self._posts_table(section, result)

    # -- sections ------------------------------------------------------------------------

    def _section_summary(self, report: Report, scope: Scope, daily_chart: bool = False) -> None:
        t = self.t
        section = report.section(t("section.summary"))
        posts = fn.post_performance(self.conn, scope)
        themes = fn.top_themes(self.conn, scope, 1)["rows"]
        theme_count = self.conn.execute(
            "SELECT COUNT(*) FROM themes WHERE day >= ? AND day <= ?"
            + (f" AND topic_id IN ({','.join('?' * len(scope.topics))})" if scope.topics else ""),
            (scope.start.isoformat(), scope.end.isoformat(), *(scope.topics or ())),
        ).fetchone()[0]
        keywords = fn.top_keywords(self.conn, scope, "keyword", 3)["rows"]
        items = fn.total_items(self.conn, scope)
        generated = sum(r["generated"] for r in posts["rows"])
        published = sum(r["published"] or 0 for r in posts["rows"])
        section.add(
            "stats",
            items=[
                (t("stat.items"), self.n(items)),
                (t("stat.themes"), self.n(theme_count)),
                (t("stat.generated"), self.n(generated)),
                (t("stat.published"), self.n(published)),
            ],
        )
        if not items:
            section.add("note", text=t("empty.period"))
            return
        if keywords:
            words = ", ".join(f"«{r['term']}»" for r in keywords)
            section.add("text", text=t("summary.keywords", words=words))
        if themes:
            top = themes[0]
            summary = self._theme_text(top["id"])
            section.add(
                "text",
                text=t(
                    "summary.top_theme",
                    theme=top["title"],
                    topic=self._topic_names.get(top["topic_id"], ""),
                    score=top["score"],
                ),
            )
            if summary:
                section.add("text", text=summary)
        if daily_chart:
            daily = fn.daily_items(self.conn, scope)
            section.add(
                "chart",
                type="daily",
                title=t("chart.daily"),
                days=[short_day(d, self.language) for d in daily["days"]],
                values=daily["totals"],
            )

    def _theme_text(self, theme_id: int) -> str | None:
        row = self.conn.execute("SELECT summary FROM themes WHERE id = ?", (theme_id,)).fetchone()
        return row["summary"] if row and row["summary"] else None

    def _section_themes(self, report: Report, scope: Scope) -> None:
        section = report.section(self.t("section.themes"))
        rows = fn.top_themes(self.conn, scope, MAX_THEMES)["rows"]
        if not rows:
            section.add("note", text=self.t("empty.themes"))
            return
        self._themes_blocks(section, rows, with_links=True)

    def _themes_blocks(self, section: Section, rows: list[dict], *, with_links: bool) -> None:
        t = self.t
        for row in rows:
            detail = self.conn.execute(
                "SELECT summary, angle FROM themes WHERE id = ?", (row["id"],)
            ).fetchone()
            links = []
            if with_links:
                links = [
                    (r["title"], r["url"])
                    for r in self.conn.execute(
                        "SELECT i.title, i.url FROM theme_items ti "
                        "JOIN items i ON i.id = ti.item_id "
                        "WHERE ti.theme_id = ? AND i.source != 'x_grok' "
                        "ORDER BY i.published_at DESC LIMIT ?",
                        (row["id"], MAX_LINKS_PER_THEME),
                    )
                ]
            meta = " · ".join(
                [
                    row.get("topic_name") or self._topic_names.get(row["topic_id"], ""),
                    format_day(row["day"], self.language),
                    t("theme.score", score=row["score"]),
                    t(f"trend.{row['trend']}"),
                    t("theme.items", count=row["item_count"]),
                ]
            )
            section.add(
                "theme",
                title=row["title"],
                meta=meta,
                summary=detail["summary"] if detail else None,
                angle=detail["angle"] if detail else None,
                angle_label=t("theme.angle"),
                links=links,
            )

    def _keywords_block(self, section: Section, result: dict[str, Any], limit: int = 15) -> None:
        rows = result["rows"][:limit]
        if not rows:
            section.add("note", text=self.t("empty.keywords"))
            return
        section.add(
            "chart",
            type="bars",
            title=self.t(f"chart.top_{result['kind']}"),
            labels=[r["term"] for r in rows],
            values=[r["count"] for r in rows],
            notes=[f"{self.n(r['share'])}%" for r in rows],
        )
        section.add("note", text=self.t("keywords.share", total=self.n(result["total_items"])))

    def _section_keywords(self, report: Report, scope: Scope) -> None:
        section = report.section(self.t("section.keywords"))
        self._keywords_block(section, fn.top_keywords(self.conn, scope, "keyword", 15))
        hashtags = fn.top_keywords(self.conn, scope, "hashtag", 15)
        if hashtags["rows"]:
            t = self.t
            section.add(
                "table",
                title=t("chart.top_hashtag"),
                header=[t("col.hashtag"), t("col.mentions"), t("col.share")],
                rows=[
                    [f"#{r['term']}", self.n(r["count"]), f"{self.n(r['share'])}%"]
                    for r in hashtags["rows"]
                ],
                align=["left", "right", "right"],
            )

    def _changes_blocks(self, section: Section, result: dict[str, Any]) -> None:
        t = self.t
        if not result["has_history"]:
            section.add("note", text=t("empty.history"))
            return
        for key in ("emerging", "declining"):
            rows = result[key]
            if not rows:
                section.add("note", text=t(f"empty.{key}"))
                continue
            section.add(
                "table",
                title=t(f"changes.{key}"),
                header=[t("col.term"), t("col.now"), t("col.before"), t("col.change")],
                rows=[
                    [
                        r["term"],
                        self.n(r["current"]),
                        self.n(r["previous"]),
                        t("changes.new") if r["change_pct"] is None else f"{r['change_pct']:+d}%",
                    ]
                    for r in rows
                ],
                align=["left", "right", "right", "right"],
            )

    def _section_changes(self, report: Report, scope: Scope) -> None:
        section = report.section(self.t("section.changes"))
        result = fn.emerging_keywords(self.conn, scope, 10)
        section.add(
            "note",
            text=self.t(
                "changes.compared",
                period=format_period(
                    result["previous"]["start"], result["previous"]["end"], self.language
                ),
            ),
        )
        self._changes_blocks(section, result)

    def _trend_blocks(self, section: Section, result: dict[str, Any]) -> None:
        if not result["series"] or not any(sum(s["values"]) for s in result["series"]):
            section.add("note", text=self.t("empty.keywords"))
            return
        days = [short_day(d, self.language) for d in result["days"]]
        section.add(
            "chart",
            type="lines",
            title=self.t("chart.trend"),
            days=days,
            series=[{"name": s["term"], "values": s["values"]} for s in result["series"][:5]],
        )

    def _section_trend(self, report: Report, scope: Scope) -> None:
        section = report.section(self.t("section.trend"))
        self._trend_blocks(section, fn.topic_trend(self.conn, scope, None, 5))

    def _groups_blocks(self, section: Section, result: dict[str, Any], kind: str) -> None:
        t = self.t
        groups = result["groups"]
        if not groups:
            section.add("note", text=t("empty.keywords"))
            return
        label = (
            (lambda k: tr(self.language, f"report.language.{k}"))
            if kind == "language"
            else (lambda k: tr(self.language, f"source.{k}"))
        )
        section.add(
            "table",
            title=t(f"compare.{kind}"),
            header=[t(f"col.{kind}"), t("col.items"), t("col.top_terms")],
            rows=[
                [
                    label(g["key"]),
                    self.n(g["items"]),
                    ", ".join(f"{x['term']} ({self.n(x['count'])})" for x in g["top"]),
                ]
                for g in groups
            ],
            align=["left", "right", "left"],
            widths=[0.2, 0.12, 0.68],
        )

    def _section_compare(self, report: Report, scope: Scope) -> None:
        section = report.section(self.t("section.compare"))
        self._groups_blocks(section, fn.compare_languages(self.conn, scope, 5), "language")
        self._groups_blocks(section, fn.compare_sources(self.conn, scope, 5), "source")

    def _posts_table(self, section: Section, result: dict[str, Any]) -> None:
        t = self.t
        if not result["rows"]:
            section.add("note", text=t("empty.posts"))
            return
        header = [t("col.platform"), t("col.generated"), t("col.published")]
        align = ["left", "right", "right"]
        metrics = ("likes", "comments", "shares", "views")
        if result.get("metrics_available"):
            header += [t(f"col.avg_{m}") for m in metrics]
            align += ["right"] * 4
        rows = []
        for r in result["rows"]:
            row = [
                tr(self.language, f"report.platform.{r['platform']}"),
                self.n(r["generated"]),
                self.n(r["published"] or 0),
            ]
            if result.get("metrics_available"):
                row += [self.n(r.get(f"avg_{m}")) for m in metrics]
            rows.append(row)
        section.add("table", header=header, rows=rows, align=align)

    def _section_posts(self, report: Report, scope: Scope) -> None:
        section = report.section(self.t("section.posts"))
        self._posts_table(section, fn.post_performance(self.conn, scope))
        start, end = scope.utc_bounds()
        params: list = [start, end]
        topic_sql = ""
        if scope.topics:
            topic_sql = f" AND d.topic_id IN ({','.join('?' * len(scope.topics))})"
            params.extend(scope.topics)
        published = self.conn.execute(
            "SELECT d.platform, d.source_label, d.text, p.published_at, p.url, r.likes, "
            "r.comments, r.shares, r.views FROM drafts d JOIN publications p ON p.draft_id = d.id "
            "LEFT JOIN post_results r ON r.draft_id = d.id "
            f"WHERE p.published_at >= ? AND p.published_at < ?{topic_sql} "
            "ORDER BY p.published_at DESC LIMIT ?",
            (*params, MAX_PUBLISHED),
        ).fetchall()
        if published:
            t = self.t
            section.add(
                "table",
                title=t("posts.published"),
                header=[t("col.date"), t("col.platform"), t("col.post"), t("col.results")],
                rows=[
                    [
                        format_day(r["published_at"][:10], self.language),
                        tr(self.language, f"report.platform.{r['platform']}"),
                        {"text": r["source_label"] or r["text"][:80], "url": r["url"]},
                        self._results_text(r),
                    ]
                    for r in published
                ],
                align=["left", "left", "left", "left"],
                widths=[0.17, 0.15, 0.4, 0.28],
            )

    def _results_text(self, row: Any) -> str:
        parts = [
            f"{self.n(row[m])} {self.t(f'metric.{m}')}"
            for m in ("likes", "comments", "shares", "views")
            if row[m] is not None
        ]
        return " · ".join(parts) or "–"

    def _section_results(self, report: Report, scope: Scope) -> None:
        t = self.t
        section = report.section(t("section.results"))
        summary = self._results.summary()
        if not summary["posts"]:
            section.add("note", text=t("empty.results"))
            return
        section.add("note", text=t("results.all_time", count=summary["posts"]))
        for reason in summary["reasons"]:
            p = reason["params"]
            section.add(
                "text",
                text=t(
                    "results.reason_platform",
                    platform=tr(self.language, f"report.platform.{p['platform']}"),
                    metric=t(f"more.{p['metric']}"),
                    value=self.n(p["value"]),
                ),
            )
        metrics = ("likes", "comments", "shares", "views")
        section.add(
            "table",
            header=[t("col.platform"), t("col.posts")]
            + [t(f"col.avg_{m}") for m in metrics]
            + [t("col.avg_interactions")],
            rows=[
                [tr(self.language, f"report.platform.{r['platform']}"), self.n(r["posts"])]
                + [self.n(r[m]) for m in metrics]
                + [self.n(r["interactions"])]
                for r in summary["platforms"]
            ],
            align=["left"] + ["right"] * 6,
        )
