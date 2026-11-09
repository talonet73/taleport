"""Insights service: Week overview, Keyword trends dashboard and 'Ask' (plan + run)."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import ValidationError

from taleport.ai import prompts
from taleport.ai.providers.base import ProviderError
from taleport.ai.service import AIService
from taleport.ai.structured import parse_answer, run_structured
from taleport.analysis.service import today_local
from taleport.ask import functions as fn
from taleport.ask.plan import PRESETS, AskPlan, ComparePeriods
from taleport.ask.scope import Filters, Period, Scope
from taleport.core.errors import AppError
from taleport.db.database import Database
from taleport.topics.service import TopicStore


class InsightsService:
    def __init__(self, db: Database, topics: TopicStore, ai: AIService) -> None:
        self._db = db
        self._topics = topics
        self._ai = ai

    def _check_topics(self, filters: Filters) -> None:
        if filters.topics:
            known = {t.id for t in self._topics.list()}
            unknown = [t for t in filters.topics if t not in known]
            if unknown:
                raise AppError("ask.unknown_topic", ids=unknown)

    # -- dashboards ----------------------------------------------------------------------

    def trends(self, period: Period, filters: Filters, today: date | None = None) -> dict[str, Any]:
        self._check_topics(filters)
        scope = Scope.build(period, filters, today)
        with self._db.connect() as conn:
            return {
                "scope": scope.to_dict(),
                "keywords": fn.top_keywords(conn, scope, "keyword", 20),
                "hashtags": fn.top_keywords(conn, scope, "hashtag", 20),
                "changes": fn.emerging_keywords(conn, scope, 10),
                "trend": fn.topic_trend(conn, scope, None, 5),
                "cloud": fn.top_keywords(conn, scope, "keyword", 60)["rows"],
                "by_language": fn.compare_languages(conn, scope, 5),
                "by_source": fn.compare_sources(conn, scope, 5),
            }

    def week(self, today: date | None = None) -> dict[str, Any]:
        scope = Scope.build(Period(preset="last_7_days"), None, today)
        with self._db.connect() as conn:
            themes_count = conn.execute(
                "SELECT COUNT(*) FROM themes WHERE day >= ? AND day <= ?",
                (scope.start.isoformat(), scope.end.isoformat()),
            ).fetchone()[0]
            posts = fn.post_performance(conn, scope)
            return {
                "scope": scope.to_dict(),
                "stats": {
                    "items": fn.total_items(conn, scope),
                    "themes": themes_count,
                    "generated": sum(r["generated"] for r in posts["rows"]),
                    "published": sum(r["published"] or 0 for r in posts["rows"]),
                },
                "daily": fn.daily_items(conn, scope),
                "themes": fn.top_themes(conn, scope, 8),
                "keywords": fn.top_keywords(conn, scope, "keyword", 10),
                "posts": posts,
            }

    # -- Ask -------------------------------------------------------------------------------

    def run_plan(self, plan: AskPlan, today: date | None = None) -> dict[str, Any]:
        results = []
        with self._db.connect() as conn:
            for step in plan.steps:
                self._check_topics(step.filters)
                if isinstance(step, ComparePeriods):
                    a = Scope.build(step.period_a, step.filters, today)
                    b = Scope.build(step.period_b, step.filters, today)
                    data = fn.compare_periods(conn, a, b, step.kind, step.limit)
                    scope_info = {"period_a": a.to_dict(), "period_b": b.to_dict()}
                else:
                    scope = Scope.build(step.period, step.filters, today)
                    scope_info = scope.to_dict()
                    match step.function:
                        case "top_keywords":
                            data = fn.top_keywords(conn, scope, step.kind, step.limit)
                        case "emerging_keywords":
                            data = fn.emerging_keywords(conn, scope, step.limit)
                        case "topic_trend":
                            data = fn.topic_trend(conn, scope, step.terms, step.limit)
                        case "compare_languages":
                            data = fn.compare_languages(conn, scope, step.limit)
                        case "compare_sources":
                            data = fn.compare_sources(conn, scope, step.limit)
                        case "top_themes":
                            data = fn.top_themes(conn, scope, step.limit)
                        case "post_performance":
                            data = fn.post_performance(conn, scope)
                results.append({"function": step.function, "scope": scope_info, "result": data})
        return {"title": plan.title, "plan": plan.model_dump(mode="json"), "steps": results}

    def run_preset(self, preset_id: str, today: date | None = None) -> dict[str, Any]:
        if preset_id not in PRESETS:
            raise AppError("ask.unknown_preset", status=404)
        plan = AskPlan.model_validate(PRESETS[preset_id])
        return {"preset": preset_id, **self.run_plan(plan, today)}

    def run_plan_json(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            plan = AskPlan.model_validate(data)
        except ValidationError as exc:
            raise AppError("ask.invalid_plan") from exc
        return self.run_plan(plan)

    def _prompt(self, question: str) -> prompts.Prompt:
        if not question.strip():
            raise AppError("ask.question_required")
        topics = "\n".join(f"- {t.id}: {t.name}" for t in self._topics.list()) or "-"
        return prompts.render(
            "ask_plan",
            self._ai.language(),
            question=question.strip(),
            topics=topics,
            today=today_local().isoformat(),
        )

    def ask(self, question: str, mode: str | None) -> dict[str, Any]:
        prompt = self._prompt(question)
        resolved, provider, fallback = self._ai.resolve(mode)
        if provider is None:
            return {"mode": "chat", "fallback": fallback, "handoff": self._ai.handoff(prompt)}
        try:
            plan = run_structured(provider, prompt, AskPlan, self._ai.recorder(provider, "ask"))
        except ProviderError as exc:
            raise AppError.from_provider(exc) from exc
        return {"mode": resolved, "question": question, **self.run_plan(plan)}

    def parse_ask(self, question: str, text: str) -> dict[str, Any]:
        plan = parse_answer(text, AskPlan)
        return {"mode": "chat", "question": question, **self.run_plan(plan)}
