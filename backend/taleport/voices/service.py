"""Tone-of-voice profiles.

A profile is a voice described as instructions (`guide`) plus a few short verbatim examples.
It is created from reference documents (the AI reads how they are written) or by hand, and
can be linked to topics: their themes are then written in that voice by default. Each topic
uses at most one profile.
"""

from __future__ import annotations

import json
from typing import Any

from taleport.ai import prompts
from taleport.ai.providers.base import ProviderError
from taleport.ai.service import AIService
from taleport.ai.structured import parse_answer, run_structured
from taleport.core.errors import AppError
from taleport.db.database import Database
from taleport.generator.extract import limit_content
from taleport.voices.schemas import VoiceAnalysis, VoiceProfileIn

MAX_PROFILES = 50
MAX_DOCUMENTS = 5
_NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"


def documents_text(documents: list[dict[str, str]]) -> tuple[str, bool]:
    """All reference documents in one block, each under its file name, within the limit."""
    if not documents:
        raise AppError("voices.no_documents")
    if len(documents) > MAX_DOCUMENTS:
        raise AppError("voices.too_many_documents", max=MAX_DOCUMENTS)
    blocks = [f"=== {d['name']} ===\n{d['text'].strip()}" for d in documents if d["text"].strip()]
    text, truncated = limit_content("\n\n".join(blocks))
    if len(text) < 200:
        raise AppError("content.too_short")
    return text, truncated


def voice_prompt_parts(voice: dict[str, Any] | None) -> tuple[str, str]:
    """(tone, style_examples) for the generation prompts."""
    if not voice:
        return "", ""
    examples = "\n\n".join(f"«{e}»" for e in voice.get("examples") or [])
    return voice.get("guide", ""), examples


class VoiceService:
    def __init__(self, db: Database, ai: AIService) -> None:
        self._db = db
        self._ai = ai

    # -- profiles ---------------------------------------------------------------------------

    @staticmethod
    def _dict(row: Any) -> dict[str, Any]:
        profile = dict(row)
        for key in ("examples", "topic_ids", "sources"):
            profile[key] = json.loads(profile[key] or "[]")
        return profile

    def list(self) -> list[dict[str, Any]]:
        with self._db.connect() as conn:
            rows = conn.execute("SELECT * FROM voice_profiles ORDER BY name COLLATE NOCASE")
            return [self._dict(r) for r in rows]

    def get(self, profile_id: int) -> dict[str, Any]:
        with self._db.connect() as conn:
            row = conn.execute(
                "SELECT * FROM voice_profiles WHERE id = ?", (profile_id,)
            ).fetchone()
        if row is None:
            raise AppError("voices.not_found", status=404)
        return self._dict(row)

    def for_topic(self, topic_id: int | None) -> dict[str, Any] | None:
        if topic_id is None:
            return None
        return next((p for p in self.list() if topic_id in p["topic_ids"]), None)

    def _known_topics(self, conn: Any, topic_ids: list[int]) -> list[int]:
        known = {r[0] for r in conn.execute("SELECT id FROM topics")}
        return [t for t in dict.fromkeys(topic_ids) if t in known]

    def _release_topics(self, conn: Any, topic_ids: list[int], keep: int | None) -> None:
        """A topic follows one voice: linking it here unlinks it from the other profiles."""
        if not topic_ids:
            return
        for row in conn.execute("SELECT id, topic_ids FROM voice_profiles"):
            if row["id"] == keep:
                continue
            current = json.loads(row["topic_ids"] or "[]")
            remaining = [t for t in current if t not in topic_ids]
            if remaining != current:
                conn.execute(
                    "UPDATE voice_profiles SET topic_ids = ? WHERE id = ?",
                    (json.dumps(remaining), row["id"]),
                )

    def create(self, data: VoiceProfileIn) -> dict[str, Any]:
        with self._db.connect() as conn:
            if conn.execute("SELECT COUNT(*) FROM voice_profiles").fetchone()[0] >= MAX_PROFILES:
                raise AppError("voices.too_many", max=MAX_PROFILES)
            topics = self._known_topics(conn, data.topic_ids)
            self._release_topics(conn, topics, keep=None)
            profile_id = conn.execute(
                "INSERT INTO voice_profiles (name, guide, examples, topic_ids, sources) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    data.name,
                    data.guide.strip(),
                    json.dumps(data.examples, ensure_ascii=False),
                    json.dumps(topics),
                    json.dumps(data.sources, ensure_ascii=False),
                ),
            ).lastrowid
        return self.get(int(profile_id or 0))

    def update(self, profile_id: int, data: VoiceProfileIn) -> dict[str, Any]:
        self.get(profile_id)
        with self._db.connect() as conn:
            topics = self._known_topics(conn, data.topic_ids)
            self._release_topics(conn, topics, keep=profile_id)
            conn.execute(
                f"UPDATE voice_profiles SET name = ?, guide = ?, examples = ?, topic_ids = ?, "
                f"sources = ?, updated_at = {_NOW} WHERE id = ?",  # noqa: S608 (constant)
                (
                    data.name,
                    data.guide.strip(),
                    json.dumps(data.examples, ensure_ascii=False),
                    json.dumps(topics),
                    json.dumps(data.sources, ensure_ascii=False),
                    profile_id,
                ),
            )
        return self.get(profile_id)

    def delete(self, profile_id: int) -> None:
        self.get(profile_id)
        with self._db.connect() as conn:
            conn.execute("DELETE FROM voice_profiles WHERE id = ?", (profile_id,))

    # -- learning a voice from documents ----------------------------------------------------

    def _analysis_prompt(self, documents: list[dict[str, str]]) -> tuple[prompts.Prompt, bool]:
        text, truncated = documents_text(documents)
        prompt = prompts.render("voice_analysis", self._ai.language(), documents=text)
        return prompt, truncated

    def analyze(self, documents: list[dict[str, str]], mode: str | None) -> dict[str, Any]:
        """Reads the voice of the documents. Nothing is saved: the user reviews it first."""
        prompt, truncated = self._analysis_prompt(documents)
        names = [d["name"] for d in documents]
        resolved, provider, fallback = self._ai.resolve(mode)
        if provider is None:
            return {
                "mode": "chat", "fallback": fallback, "truncated": truncated,
                "handoff": self._ai.handoff(prompt),
            }  # fmt: skip
        try:
            analysis = run_structured(
                provider, prompt, VoiceAnalysis, self._ai.recorder(provider, "voice_analysis"),
                max_tokens=4000,
            )  # fmt: skip
        except ProviderError as exc:
            raise AppError.from_provider(exc) from exc
        return {
            "mode": resolved,
            "truncated": truncated,
            "voice": self._suggestion(analysis, names),
        }

    def parse_analysis(self, names: list[str], text: str) -> dict[str, Any]:
        analysis = parse_answer(text, VoiceAnalysis)
        return {"mode": "chat", "voice": self._suggestion(analysis, names)}

    @staticmethod
    def _suggestion(analysis: VoiceAnalysis, names: list[str]) -> dict[str, Any]:
        fallback_name = names[0].rsplit(".", 1)[0] if names else ""
        return {
            "name": analysis.name or fallback_name,
            "guide": analysis.guide,
            "examples": analysis.examples,
            "sources": names,
        }
