"""Post generator: drafts from a hot theme or from long content, with fact-check warnings.

Like every AI feature it works with a provider or through "Open in chat" (prompt + pasted
answer). Each draft keeps a snapshot of its sources, so it can be regenerated and
re-checked even after the day's themes are recomputed.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any

from taleport.ai import prompts
from taleport.ai.providers.base import ProviderError
from taleport.ai.service import AIService
from taleport.ai.structured import parse_answer, run_structured
from taleport.core.errors import AppError
from taleport.db.database import Database
from taleport.generator.covered import published_themes
from taleport.generator.extract import limit_content
from taleport.generator.factcheck import check_facts
from taleport.generator.render import render_copy_text
from taleport.generator.schemas import GeneratedPost, GeneratedPosts
from taleport.topics.models import Topic
from taleport.topics.service import TopicStore

PLATFORMS = ("linkedin", "instagram", "facebook", "youtube", "tiktok")
LANGUAGES = ("it", "en", "es")
MAX_POSTS_PER_REQUEST = 12
MAX_SERIES = 10
MAX_SOURCES = 12
GENERATION_MAX_TOKENS = 16_000
RESULT_COLUMNS = ("likes", "comments", "shares", "views")
_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def _validate_choice(platforms: list[str], languages: list[str]) -> None:
    if not platforms or any(p not in PLATFORMS for p in platforms):
        raise AppError("generator.platforms_required")
    if not languages or any(lang not in LANGUAGES for lang in languages):
        raise AppError("generator.languages_required")


class GeneratorService:
    def __init__(self, db: Database, ai: AIService, topics: TopicStore) -> None:
        self._db = db
        self._ai = ai
        self._topics = topics

    # -- prompt context ------------------------------------------------------------------

    @staticmethod
    def _style(topic: Topic | None) -> str:
        if not topic or not topic.style_examples:
            return "-"
        return "\n\n".join(f"«{example}»" for example in topic.style_examples)

    def _covered(self, conn: sqlite3.Connection, topic_id: int | None, extra: str = "") -> str:
        lines = []
        if topic_id is not None:
            lines = [f"- {title or key}" for key, title in published_themes(conn, topic_id)]
        if extra:
            lines.append(extra)
        return "\n".join(lines) or "-"

    def _theme_context(self, theme_id: int) -> dict[str, Any]:
        with self._db.connect() as conn:
            theme = conn.execute("SELECT * FROM themes WHERE id = ?", (theme_id,)).fetchone()
            if theme is None:
                raise AppError("themes.not_found", status=404)
            rows = conn.execute(
                "SELECT i.source, i.url, i.title, i.excerpt, i.publisher, i.extra "
                "FROM theme_items ti JOIN items i ON i.id = ti.item_id WHERE ti.theme_id = ? "
                "ORDER BY i.source = 'x_grok' DESC, i.published_at DESC",
                (theme_id,),
            ).fetchall()
        sources: list[dict[str, str]] = []
        corpus_parts: list[str] = []
        for row in rows[:MAX_SOURCES]:
            text = row["excerpt"]
            if row["source"] == "x_grok":
                text = json.loads(row["extra"]).get("text", "")[:3000]
            sources.append(
                {
                    "title": row["title"],
                    "url": row["url"],
                    "publisher": row["publisher"],
                    "text": text,
                }
            )
            corpus_parts += [row["title"], text]
        return {
            "topic_id": theme["topic_id"],
            "theme_id": theme_id,
            "theme_key": theme["key"],
            "theme_title": theme["title"],
            "theme_summary": theme["summary"] or "",
            "sources": sources,
            "corpus": "\n".join(corpus_parts),
        }

    @staticmethod
    def _sources_text(sources: list[dict[str, str]]) -> str:
        blocks = []
        for n, source in enumerate(sources, start=1):
            head = f"[{n}] {source['title']}" + (
                f" — {source['publisher']}" if source["publisher"] else ""
            )
            blocks.append(f"{head}\n{source['url']}\n{source['text']}".strip())
        return "\n\n".join(blocks) or "-"

    def _theme_prompt(
        self,
        ctx: dict[str, Any],
        platforms: list[str],
        languages: list[str],
        variants: int,
        tone: str | None,
        avoid: str = "",
    ) -> prompts.Prompt:
        ui = self._ai.language()
        topic = self._topics.get(ctx["topic_id"]) if ctx.get("topic_id") else None
        with self._db.connect() as conn:
            covered = self._covered(conn, ctx.get("topic_id"), avoid)
        return prompts.render(
            "post_generation",
            ui,
            topic_name=topic.name if topic else "-",
            topic_description=(topic.description if topic else "") or "-",
            audience=(topic.audience if topic else "") or "-",
            tone=tone or (topic.tone if topic else "") or "-",
            style_examples=self._style(topic),
            covered=covered,
            theme_title=ctx["theme_title"],
            theme_summary=ctx["theme_summary"],
            sources=self._sources_text(ctx["sources"]),
            platforms=", ".join(platforms),
            languages=prompts.language_list(languages, ui),
            variants=str(variants),
        )

    def _long_prompt(
        self, ctx: dict[str, Any], count: int, platforms: list[str], language: str, avoid: str = ""
    ) -> prompts.Prompt:
        ui = self._ai.language()
        topic = self._topics.get(ctx["topic_id"]) if ctx.get("topic_id") else None
        title = ctx["theme_title"] + (f" — {avoid}" if avoid else "")
        return prompts.render(
            "long_content",
            ui,
            content_title=title,
            audience=(topic.audience if topic else "") or "-",
            tone=(topic.tone if topic else "") or "-",
            style_examples=self._style(topic),
            content=ctx["corpus"],
            count=str(count),
            platforms=", ".join(platforms),
            languages=prompts.language_list([language], ui),
        )

    # -- running ---------------------------------------------------------------------------

    def _run(self, prompt: prompts.Prompt, mode: str | None, feature: str) -> tuple[str, Any]:
        """('chat', envelope) for a handoff, or (mode, GeneratedPosts)."""
        resolved, provider, fallback = self._ai.resolve(mode)
        if provider is None:
            return "chat", {
                "mode": "chat",
                "fallback": fallback,
                "handoff": self._ai.handoff(prompt),
            }
        try:
            posts = run_structured(
                provider, prompt, GeneratedPosts, self._ai.recorder(provider, feature),
                max_tokens=GENERATION_MAX_TOKENS,
            )  # fmt: skip
        except ProviderError as exc:
            raise AppError.from_provider(exc) from exc
        return resolved, posts

    def _allowed_terms(self, topic_id: int | None) -> list[str]:
        if not topic_id:
            return []
        topic = self._topics.get(topic_id)
        words = [w for lang in topic.languages for w in topic.keywords_for(lang)]
        return [topic.name, *words, *topic.hashtags, *topic.exclude]

    def _save(
        self,
        posts: list[GeneratedPost],
        ctx: dict[str, Any],
        origin: str,
        mode: str,
    ) -> dict[str, Any]:
        batch_id = uuid.uuid4().hex[:12]
        allowed = self._allowed_terms(ctx.get("topic_id"))
        ui = self._ai.language()
        snapshot = json.dumps(ctx, ensure_ascii=False)
        ids: list[int] = []
        with self._db.connect() as conn:
            for post in posts:
                text = render_copy_text(post, ui)
                used = [
                    {"title": ctx["sources"][n - 1]["title"], "url": ctx["sources"][n - 1]["url"]}
                    for n in post.sources_used
                    if 1 <= n <= len(ctx["sources"])
                ]
                cursor = conn.execute(
                    "INSERT INTO drafts (batch_id, topic_id, theme_id, theme_key, theme_title, "
                    "origin, source_label, platform, language, variant, series_index, content, "
                    "text, sources, "
                    "fact_warnings, image_idea, image_prompt, context, ai_mode) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        batch_id,
                        ctx.get("topic_id"),
                        ctx.get("theme_id"),
                        ctx.get("theme_key"),
                        ctx.get("theme_title"),
                        origin,
                        ctx["theme_title"],
                        post.platform,
                        post.language,
                        post.variant,
                        post.series_index,
                        post.model_dump_json(),
                        text,
                        json.dumps(used, ensure_ascii=False),
                        json.dumps(check_facts(text, ctx["corpus"], allowed), ensure_ascii=False),
                        post.image_idea,
                        post.image_prompt,
                        snapshot,
                        mode,
                    ),
                )
                ids.append(int(cursor.lastrowid or 0))
        return {"mode": mode, "batch_id": batch_id, "drafts": [self.get(i) for i in ids]}

    @staticmethod
    def _keep_requested(
        posts: GeneratedPosts, platforms: list[str], languages: list[str]
    ) -> list[GeneratedPost]:
        kept = [p for p in posts.posts if p.platform in platforms and p.language in languages]
        if not kept:
            raise AppError("generator.no_posts")
        return kept[: MAX_POSTS_PER_REQUEST + MAX_SERIES * len(PLATFORMS)]

    # -- from a theme --------------------------------------------------------------------

    def _check_theme_request(
        self, platforms: list[str], languages: list[str], variants: int
    ) -> None:
        _validate_choice(platforms, languages)
        if not 1 <= variants <= 3:
            raise AppError("generator.variants_range")
        if len(platforms) * len(languages) * variants > MAX_POSTS_PER_REQUEST:
            raise AppError("generator.too_many", max=MAX_POSTS_PER_REQUEST)

    def generate_from_theme(
        self,
        theme_id: int,
        platforms: list[str],
        languages: list[str],
        variants: int = 1,
        tone: str | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        self._check_theme_request(platforms, languages, variants)
        ctx = self._theme_context(theme_id)
        prompt = self._theme_prompt(ctx, platforms, languages, variants, tone)
        resolved, outcome = self._run(prompt, mode, "post_generation")
        if resolved == "chat":
            return outcome
        return self._save(
            self._keep_requested(outcome, platforms, languages), ctx, "theme", resolved
        )

    def parse_from_theme(
        self, theme_id: int, platforms: list[str], languages: list[str], text: str
    ) -> dict[str, Any]:
        _validate_choice(platforms, languages)
        ctx = self._theme_context(theme_id)
        posts = parse_answer(text, GeneratedPosts)
        return self._save(self._keep_requested(posts, platforms, languages), ctx, "theme", "chat")

    # -- from long content -----------------------------------------------------------------

    def _long_context(self, content: str, title: str, topic_id: int | None) -> tuple[dict, bool]:
        text, truncated = limit_content(content)
        if len(text) < 200:
            raise AppError("content.too_short")
        if topic_id is not None:
            self._topics.get(topic_id)
        label = title.strip() or text.split("\n", 1)[0][:80]
        ctx = {
            "topic_id": topic_id,
            "theme_id": None,
            "theme_key": None,
            "theme_title": label,
            "theme_summary": "",
            "sources": [],
            "corpus": text,
        }
        return ctx, truncated

    def generate_long(
        self,
        content: str,
        title: str,
        count: int,
        platforms: list[str],
        language: str,
        topic_id: int | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        _validate_choice(platforms, [language])
        if not 1 <= count <= MAX_SERIES:
            raise AppError("generator.series_range", max=MAX_SERIES)
        ctx, truncated = self._long_context(content, title, topic_id)
        prompt = self._long_prompt(ctx, count, platforms, language)
        resolved, outcome = self._run(prompt, mode, "long_content")
        if resolved == "chat":
            return {**outcome, "truncated": truncated}
        saved = self._save(
            self._keep_requested(outcome, platforms, [language]), ctx, "long_content", resolved
        )
        return {**saved, "truncated": truncated}

    def parse_long(
        self,
        content: str,
        title: str,
        platforms: list[str],
        language: str,
        topic_id: int | None,
        text: str,
    ) -> dict[str, Any]:
        _validate_choice(platforms, [language])
        ctx, truncated = self._long_context(content, title, topic_id)
        posts = parse_answer(text, GeneratedPosts)
        saved = self._save(
            self._keep_requested(posts, platforms, [language]), ctx, "long_content", "chat"
        )
        return {**saved, "truncated": truncated}

    # -- single drafts ---------------------------------------------------------------------

    def _row(self, conn: sqlite3.Connection, draft_id: int) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if row is None:
            raise AppError("drafts.not_found", status=404)
        return row

    def _regenerate_prompt(self, row: sqlite3.Row) -> prompts.Prompt:
        ctx = json.loads(row["context"])
        avoid = row["text"][:600]
        if row["origin"] == "long_content":
            return self._long_prompt(ctx, 1, [row["platform"]], row["language"], avoid=avoid)
        return self._theme_prompt(ctx, [row["platform"]], [row["language"]], 1, None, avoid=avoid)

    def regenerate(self, draft_id: int, mode: str | None = None) -> dict[str, Any]:
        with self._db.connect() as conn:
            row = self._row(conn, draft_id)
        resolved, outcome = self._run(self._regenerate_prompt(row), mode, "post_regeneration")
        if resolved == "chat":
            return outcome
        return {"mode": resolved, "draft": self._replace(row, outcome)}

    def parse_regenerate(self, draft_id: int, text: str) -> dict[str, Any]:
        with self._db.connect() as conn:
            row = self._row(conn, draft_id)
        return {"mode": "chat", "draft": self._replace(row, parse_answer(text, GeneratedPosts))}

    def _replace(self, row: sqlite3.Row, posts: GeneratedPosts) -> dict[str, Any]:
        candidates = [
            p
            for p in posts.posts
            if p.platform == row["platform"] and p.language == row["language"]
        ]
        if not candidates:
            raise AppError("generator.no_posts")
        post = candidates[0].model_copy(
            update={"variant": row["variant"], "series_index": row["series_index"]}
        )
        ctx = json.loads(row["context"])
        text = render_copy_text(post, self._ai.language())
        warnings = check_facts(text, ctx.get("corpus", ""), self._allowed_terms(row["topic_id"]))
        used = [
            {"title": ctx["sources"][n - 1]["title"], "url": ctx["sources"][n - 1]["url"]}
            for n in post.sources_used
            if 1 <= n <= len(ctx.get("sources", []))
        ]
        with self._db.connect() as conn:
            conn.execute(
                f"UPDATE drafts SET content = ?, text = ?, edited = 0, sources = ?, "
                f"fact_warnings = ?, "
                f"image_idea = ?, image_prompt = ?, updated_at = {_NOW} WHERE id = ?",
                (
                    post.model_dump_json(),
                    text,
                    json.dumps(used, ensure_ascii=False),
                    json.dumps(warnings, ensure_ascii=False),
                    post.image_idea,
                    post.image_prompt,
                    row["id"],
                ),
            )
        return self.get(row["id"])

    def update_text(self, draft_id: int, text: str) -> dict[str, Any]:
        if not text.strip():
            raise AppError("drafts.empty")
        with self._db.connect() as conn:
            row = self._row(conn, draft_id)
            ctx = json.loads(row["context"])
            warnings = check_facts(
                text, ctx.get("corpus", ""), self._allowed_terms(row["topic_id"])
            )
            conn.execute(
                f"UPDATE drafts SET text = ?, edited = 1, fact_warnings = ?, updated_at = {_NOW} "
                "WHERE id = ?",
                (text.strip(), json.dumps(warnings, ensure_ascii=False), draft_id),
            )
        return self.get(draft_id)

    def schedule(self, draft_id: int, scheduled_at: str | None) -> dict[str, Any]:
        if scheduled_at is not None:
            try:
                datetime.fromisoformat(scheduled_at)
            except ValueError as exc:
                raise AppError("validation", fields=["scheduled_at"]) from exc
        with self._db.connect() as conn:
            row = self._row(conn, draft_id)
            status = row["status"]
            if status != "published":
                status = "scheduled" if scheduled_at else "draft"
            conn.execute(
                f"UPDATE drafts SET scheduled_at = ?, status = ?, updated_at = {_NOW} WHERE id = ?",
                (scheduled_at, status, draft_id),
            )
        return self.get(draft_id)

    def publish(
        self, draft_id: int, url: str | None = None, published_at: str | None = None
    ) -> dict:
        if url and not url.startswith(("https://", "http://")):
            raise AppError("invalid_url")
        when = published_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self._db.connect() as conn:
            row = self._row(conn, draft_id)
            conn.execute("DELETE FROM publications WHERE draft_id = ?", (draft_id,))
            conn.execute(
                "INSERT INTO publications (draft_id, platform, published_at, url) "
                "VALUES (?, ?, ?, ?)",
                (draft_id, row["platform"], when, url or None),
            )
            conn.execute(
                f"UPDATE drafts SET status = 'published', updated_at = {_NOW} WHERE id = ?",
                (draft_id,),
            )
        return self.get(draft_id)

    def unpublish(self, draft_id: int) -> dict[str, Any]:
        with self._db.connect() as conn:
            row = self._row(conn, draft_id)
            conn.execute("DELETE FROM publications WHERE draft_id = ?", (draft_id,))
            status = "scheduled" if row["scheduled_at"] else "draft"
            conn.execute(
                f"UPDATE drafts SET status = ?, updated_at = {_NOW} WHERE id = ?",
                (status, draft_id),
            )
        return self.get(draft_id)

    def delete(self, draft_id: int) -> None:
        with self._db.connect() as conn:
            self._row(conn, draft_id)
            conn.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))

    # -- reading -------------------------------------------------------------------------

    @staticmethod
    def to_dict(row: sqlite3.Row, publication: sqlite3.Row | None = None) -> dict[str, Any]:
        data = {k: row[k] for k in row.keys() if k != "context"}  # noqa: SIM118
        data["content"] = json.loads(row["content"])
        data["sources"] = json.loads(row["sources"])
        data["fact_warnings"] = json.loads(row["fact_warnings"])
        data["edited"] = bool(row["edited"])
        data["publication"] = dict(publication) if publication else None
        return data

    @classmethod
    def list_row(cls, row: sqlite3.Row) -> dict[str, Any]:
        """A draft read with its publication (pub_at, pub_url) and results columns joined."""
        item = cls.to_dict(row, None)
        for key in ("pub_at", "pub_url", *RESULT_COLUMNS):
            item.pop(key, None)
        if row["pub_at"]:
            item["publication"] = {"published_at": row["pub_at"], "url": row["pub_url"]}
        has_results = any(row[m] is not None for m in RESULT_COLUMNS)
        item["results"] = {m: row[m] for m in RESULT_COLUMNS} if has_results else None
        return item

    def get(self, draft_id: int) -> dict[str, Any]:
        with self._db.connect() as conn:
            row = self._row(conn, draft_id)
            publication = conn.execute(
                "SELECT published_at, url FROM publications WHERE draft_id = ?", (draft_id,)
            ).fetchone()
            results = conn.execute(
                "SELECT likes, comments, shares, views FROM post_results WHERE draft_id = ?",
                (draft_id,),
            ).fetchone()
        data = self.to_dict(row, publication)
        data["results"] = dict(results) if results else None
        return data

    def list_drafts(
        self, limit: int = 50, batch_id: str | None = None, status: str | None = None
    ) -> list[dict[str, Any]]:
        clauses, params = [], []
        if batch_id:
            clauses.append("d.batch_id = ?")
            params.append(batch_id)
        if status:
            clauses.append("d.status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._db.connect() as conn:
            rows = conn.execute(
                f"SELECT d.*, p.published_at AS pub_at, p.url AS pub_url, r.likes, r.comments, "
                f"r.shares, r.views FROM drafts d LEFT JOIN publications p ON p.draft_id = d.id "
                f"LEFT JOIN post_results r ON r.draft_id = d.id {where} "
                "ORDER BY d.id DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
        return [self.list_row(row) for row in rows]
