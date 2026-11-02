"""AI features: theme insights, "Create with AI" for topics, "Search X with Grok".

Every feature works in two ways:
- with a provider (Ollama or an API key): the app calls it and applies the validated result;
- "Open in chat": the app prepares the prompt (copied to the clipboard) and opens the chat
  site; the user pastes the answer back and the same validation/apply step runs.
When the chosen provider is not available (no key, Ollama not running) the feature falls
back to "Open in chat" and says why.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any
from urllib.parse import quote

from taleport.ai import prompts
from taleport.ai.handoff import build_handoff
from taleport.ai.providers.base import Completion, LLMProvider, ProviderError
from taleport.ai.registry import build_provider, build_x_search_provider
from taleport.ai.schemas import ThemeInsights, TopicSuggestion
from taleport.ai.structured import parse_answer, run_structured
from taleport.ai.usage import UsageStore
from taleport.analysis.service import today_local
from taleport.collectors.base import CollectedItem
from taleport.collectors.text import canonical_url, excerpt
from taleport.core import clipboard
from taleport.core.errors import AppError
from taleport.core.secrets import SecretStore
from taleport.core.settings import AppSettings, SettingsStore
from taleport.db.database import Database
from taleport.scan.items import ItemRepository
from taleport.topics.editions import EDITIONS
from taleport.topics.models import Topic
from taleport.topics.service import TopicStore

log = logging.getLogger(__name__)

X_SEARCH_DAYS = 3
MAX_ITEMS_PER_THEME_IN_PROMPT = 6
MAX_X_TEXT = 20_000

ProviderFactory = Callable[[str, AppSettings, SecretStore], LLMProvider]


def _as_app_error(exc: ProviderError) -> AppError:
    return AppError(exc.code, status=502, **exc.params)


class AIService:
    def __init__(
        self,
        db: Database,
        settings: SettingsStore,
        secrets: SecretStore,
        topics: TopicStore,
        items: ItemRepository,
        usage: UsageStore,
        provider_factory: ProviderFactory = build_provider,
        x_provider_factory: Callable[..., LLMProvider] = build_x_search_provider,
        clipboard: Callable[[str], bool] | None = None,
    ) -> None:
        self._db = db
        self._settings = settings
        self._secrets = secrets
        self._topics = topics
        self._items = items
        self._usage = usage
        self._factory = provider_factory
        self._x_factory = x_provider_factory
        self._clipboard = clipboard

    # -- plumbing ------------------------------------------------------------------------

    def resolve(self, requested: str | None) -> tuple[str, LLMProvider | None, str | None]:
        """(mode, provider or None for chat, fallback reason)."""
        settings = self._settings.get()
        mode = requested or settings.default_ai
        if mode == "chat":
            return "chat", None, None
        try:
            return mode, self._factory(mode, settings, self._secrets), None
        except ProviderError as exc:
            log.info("AI provider %s unavailable (%s): falling back to chat", mode, exc.code)
            return "chat", None, exc.code

    def handoff(self, prompt: prompts.Prompt, site: str | None = None) -> dict[str, Any]:
        settings = self._settings.get()
        handoff = build_handoff(
            site or settings.chat_site,
            prompts.as_single_text(prompt),
            prefill=settings.chat_prefill,
        )
        copy = self._clipboard or clipboard.copy_text  # looked up late: replaceable in tests
        return {**handoff.to_dict(), "copied": copy(handoff.prompt)}

    def recorder(self, provider: LLMProvider, feature: str) -> Callable[[Completion], None]:
        return lambda completion: self._usage.record(
            provider.name, feature, completion, paid=provider.paid
        )

    def language(self) -> str:
        return self._settings.get().language

    # -- Create with AI (topics) -----------------------------------------------------------

    def _topic_prompt(self, description: str, editions: list[str]) -> prompts.Prompt:
        languages = list(dict.fromkeys(EDITIONS[c].language for c in editions if c in EDITIONS))
        if not description.strip():
            raise AppError("ai.description_required")
        return prompts.render(
            "topic_suggestion",
            self.language(),
            description=description.strip(),
            languages=prompts.language_list(languages or ["it"], self.language()),
        )

    @staticmethod
    def _clean_suggestion(suggestion: TopicSuggestion, editions: list[str]) -> dict[str, Any]:
        languages = {EDITIONS[c].language for c in editions if c in EDITIONS} or {"it"}
        data = suggestion.model_dump()
        data["keywords"] = {k: v for k, v in data["keywords"].items() if k in languages and v}
        data["sources"] = [
            s for s in data["sources"] if s["kind"] in ("rss", "youtube_channel", "subreddit")
        ]
        allowed = {"linkedin", "instagram", "facebook", "youtube", "tiktok"}
        data["platforms"] = [p for p in data["platforms"] if p in allowed]
        return data

    def suggest_topic(self, description: str, editions: list[str], mode: str | None) -> dict:
        prompt = self._topic_prompt(description, editions)
        mode, provider, fallback = self.resolve(mode)
        if provider is None:
            return {"mode": "chat", "fallback": fallback, "handoff": self.handoff(prompt)}
        try:
            result = run_structured(
                provider, prompt, TopicSuggestion, self.recorder(provider, "topic_suggestion")
            )
        except ProviderError as exc:
            raise _as_app_error(exc) from exc
        return {"mode": mode, "result": self._clean_suggestion(result, editions)}

    def parse_topic_suggestion(self, text: str, editions: list[str]) -> dict:
        return {
            "mode": "chat",
            "result": self._clean_suggestion(parse_answer(text, TopicSuggestion), editions),
        }

    # -- Theme insights ------------------------------------------------------------------

    def _theme_prompt(self, topic: Topic, day: date) -> prompts.Prompt:
        with self._db.connect() as conn:
            themes = conn.execute(
                "SELECT id, title, related_terms, item_count FROM themes "
                "WHERE topic_id = ? AND day = ? ORDER BY position",
                (topic.id, day.isoformat()),
            ).fetchall()
            if not themes:
                raise AppError("ai.no_themes")
            blocks = []
            for theme in themes:
                items = conn.execute(
                    "SELECT i.source, i.title, i.excerpt FROM theme_items ti "
                    "JOIN items i ON i.id = ti.item_id WHERE ti.theme_id = ? LIMIT ?",
                    (theme["id"], MAX_ITEMS_PER_THEME_IN_PROMPT),
                ).fetchall()
                lines = [
                    f"- [{i['source']}] {i['title']}"
                    + (f" — {i['excerpt'][:160]}" if i["excerpt"] else "")
                    for i in items
                ]
                # Language-neutral layout: the template explains it in the UI language.
                related = ", ".join(json.loads(theme["related_terms"]))
                blocks.append(
                    f"id {theme['id']}: «{theme['title']}» (n={theme['item_count']}"
                    + (f"; + {related}" if related else "")
                    + ")\n"
                    + "\n".join(lines)
                )
        return prompts.render(
            "theme_insights",
            self.language(),
            topic_name=topic.name,
            topic_description=topic.description or "-",
            topic_audience=topic.audience or "-",
            themes="\n\n".join(blocks),
        )

    def theme_insights(self, topic_id: int, mode: str | None, day: date | None = None) -> dict:
        day = day or today_local()
        topic = self._topics.get(topic_id)
        prompt = self._theme_prompt(topic, day)
        mode, provider, fallback = self.resolve(mode)
        if provider is None:
            return {"mode": "chat", "fallback": fallback, "handoff": self.handoff(prompt)}
        try:
            insights = run_structured(
                provider, prompt, ThemeInsights, self.recorder(provider, "theme_insights")
            )
        except ProviderError as exc:
            raise _as_app_error(exc) from exc
        return {"mode": mode, "updated": self.apply_theme_insights(topic_id, day, insights)}

    def parse_theme_insights(self, topic_id: int, text: str, day: date | None = None) -> dict:
        day = day or today_local()
        insights = parse_answer(text, ThemeInsights)
        return {"mode": "chat", "updated": self.apply_theme_insights(topic_id, day, insights)}

    def apply_theme_insights(self, topic_id: int, day: date, insights: ThemeInsights) -> int:
        """Write AI titles/summaries/angles; merge themes the AI says are the same story."""
        with self._db.connect() as conn:
            known = {
                r["id"]: dict(r)
                for r in conn.execute(
                    "SELECT id, score FROM themes WHERE topic_id = ? AND day = ?",
                    (topic_id, day.isoformat()),
                )
            }
            updated = 0
            for insight in insights.themes:
                if insight.id not in known:
                    continue
                conn.execute(
                    "UPDATE themes SET title = ?, summary = ?, angle = ?, origin = 'ai' "
                    "WHERE id = ?",
                    (insight.title, insight.summary or None, insight.angle or None, insight.id),
                )
                updated += 1
            for insight in insights.themes:
                target = insight.same_as
                if insight.id not in known or target not in known or target == insight.id:
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO theme_items (theme_id, item_id) "
                    "SELECT ?, item_id FROM theme_items WHERE theme_id = ?",
                    (target, insight.id),
                )
                conn.execute("DELETE FROM themes WHERE id = ?", (insight.id,))
                conn.execute(
                    "UPDATE themes SET score = MAX(score, ?), "
                    "item_count = (SELECT COUNT(*) FROM theme_items WHERE theme_id = ?), "
                    "source_count = (SELECT COUNT(DISTINCT i.source) FROM theme_items ti "
                    "JOIN items i ON i.id = ti.item_id WHERE ti.theme_id = ?) WHERE id = ?",
                    (known[insight.id]["score"], target, target, target),
                )
                known.pop(insight.id)
            remaining = conn.execute(
                "SELECT id FROM themes WHERE topic_id = ? AND day = ? ORDER BY score DESC, id",
                (topic_id, day.isoformat()),
            ).fetchall()
            for position, row in enumerate(remaining):
                conn.execute("UPDATE themes SET position = ? WHERE id = ?", (position, row["id"]))
        return updated

    # -- Search X with Grok --------------------------------------------------------------

    def _x_context(self, theme_id: int | None, topic_id: int | None) -> dict[str, Any]:
        with self._db.connect() as conn:
            if theme_id is not None:
                row = conn.execute(
                    "SELECT id, topic_id, key, title, related_terms FROM themes WHERE id = ?",
                    (theme_id,),
                ).fetchone()
                if row is None:
                    raise AppError("themes.not_found", status=404)
                topic = self._topics.get(row["topic_id"])
                # Search by the theme's key phrase, not by a (possibly AI-written) long title.
                terms = [row["key"], *json.loads(row["related_terms"])[:3]]
                return {
                    "topic": topic,
                    "theme_id": row["id"],
                    "title": row["title"],
                    "terms": terms,
                }
        if topic_id is None:
            raise AppError("validation", fields=["theme_id", "topic_id"])
        topic = self._topics.get(topic_id)
        terms = [w for lang in topic.languages for w in topic.keywords_for(lang)][:6]
        return {"topic": topic, "theme_id": None, "title": topic.name, "terms": terms}

    def _x_prompt(self, ctx: dict[str, Any]) -> prompts.Prompt:
        topic: Topic = ctx["topic"]
        query = " OR ".join(f'"{t}"' if " " in t else t for t in ctx["terms"] if t)
        if topic.hashtags:
            query += " " + " ".join(f"#{tag}" for tag in topic.hashtags[:3])
        return prompts.render(
            "x_search",
            self.language(),
            days=str(X_SEARCH_DAYS),
            query=query,
            languages=prompts.language_list(topic.languages, self.language()),
            context=f"{topic.name} — {ctx['title']}",
        )

    def x_search(self, theme_id: int | None, topic_id: int | None, mode: str) -> dict:
        ctx = self._x_context(theme_id, topic_id)
        prompt = self._x_prompt(ctx)
        if mode != "xai":
            return {"mode": "chat", "handoff": self.handoff(prompt, site="grok")}
        today = today_local()
        try:
            provider = self._x_factory(
                self._settings.get(),
                self._secrets,
                (today - timedelta(days=X_SEARCH_DAYS)).isoformat(),
                today.isoformat(),
            )
            completion = provider.complete(
                prompt.system, prompt.user, json_output=False, max_tokens=4000
            )
        except ProviderError as exc:
            raise _as_app_error(exc) from exc
        self.recorder(provider, "x_search")(completion)
        item_id = self._save_x_report(ctx, completion.text, completion.citations, via="api")
        return {"mode": "xai", "item_id": item_id}

    def save_x_report(self, theme_id: int | None, topic_id: int | None, text: str) -> dict:
        if not text.strip():
            raise AppError("ai.empty_answer")
        ctx = self._x_context(theme_id, topic_id)
        return {"mode": "chat", "item_id": self._save_x_report(ctx, text, [], via="chat")}

    def _save_x_report(
        self, ctx: dict[str, Any], text: str, citations: list[str], *, via: str
    ) -> int:
        topic: Topic = ctx["topic"]
        query = " ".join(ctx["terms"][:3])
        stamp = int(time.time())
        owner = f"t{ctx['theme_id']}" if ctx["theme_id"] else f"p{topic.id}"
        url = f"https://x.com/search?q={quote(query)}&f=live&taleport={owner}-{stamp}"
        item = CollectedItem(
            source="x_grok",
            url=url,
            title=f"X · {ctx['title']}",
            excerpt=excerpt(text),
            language=self.language(),
            publisher="X via Grok",
            extra={"text": text.strip()[:MAX_X_TEXT], "via": via, "citations": citations},
        )
        self._items.save([item], topic.id, None)
        with self._db.connect() as conn:
            item_id = conn.execute(
                "SELECT id FROM items WHERE canonical_url = ?", (canonical_url(url),)
            ).fetchone()["id"]
            if ctx["theme_id"]:
                conn.execute(
                    "INSERT OR IGNORE INTO theme_items (theme_id, item_id) VALUES (?, ?)",
                    (ctx["theme_id"], item_id),
                )
        return item_id

    # -- connection test -------------------------------------------------------------------

    def test_provider(self, provider_id: str) -> dict:
        settings = self._settings.get()
        started = time.monotonic()
        try:
            provider = self._factory(provider_id, settings, self._secrets)
            completion = provider.complete(
                "You are a connection test.", "Reply with the single word OK.", json_output=False,
                max_tokens=300,
            )  # fmt: skip
        except ProviderError as exc:
            raise _as_app_error(exc) from exc
        self.recorder(provider, "connection_test")(completion)
        return {
            "ok": True,
            "model": completion.model,
            "latency_ms": round((time.monotonic() - started) * 1000),
        }
