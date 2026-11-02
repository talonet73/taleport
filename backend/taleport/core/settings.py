"""App settings: a validated model persisted as key/JSON rows in the `settings` table."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from taleport.core.errors import AppError
from taleport.db.database import Database

log = logging.getLogger(__name__)

Language = Literal["it", "en", "es"]
Theme = Literal["dark", "light", "system"]
AiMode = Literal["chat", "ollama", "anthropic", "openai", "xai", "perplexity", "gemini"]
ChatSite = Literal["claude", "chatgpt", "grok", "perplexity"]


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    language: Language = "it"
    theme: Theme = "dark"
    default_ai: AiMode = "chat"
    scan_time: str = Field("07:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    start_with_windows: bool = False
    close_to_tray: bool = True
    first_run_completed: bool = False
    # AI layer (phase 4)
    ai_models: dict[str, str] = Field(default_factory=dict)  # provider -> model; empty = default
    ollama_url: str = Field("http://localhost:11434", pattern=r"^https?://\S+$")
    chat_site: ChatSite = "claude"
    chat_prefill: bool = False  # experimental: put short prompts in the chat site's URL
    ai_auto_insights: bool = True  # after each scan, if the default AI is not "chat"


SettingsListener = Callable[[AppSettings, AppSettings], None]


class SettingsStore:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._listeners: list[SettingsListener] = []

    def add_listener(self, listener: SettingsListener) -> None:
        """Called with (old, new) after every successful update."""
        self._listeners.append(listener)

    def get(self) -> AppSettings:
        with self._db.connect() as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
        stored = {row["key"]: json.loads(row["value"]) for row in rows}
        values: dict[str, Any] = {}
        # Validate field by field so one bad stored value falls back to its default
        # instead of discarding every setting.
        for name in AppSettings.model_fields:
            if name not in stored:
                continue
            try:
                AppSettings.model_validate({name: stored[name]})
            except ValidationError:
                continue
            values[name] = stored[name]
        return AppSettings.model_validate(values)

    def update(self, changes: dict[str, Any]) -> AppSettings:
        current = self.get()
        try:
            updated = AppSettings.model_validate(current.model_dump() | changes)
        except ValidationError as exc:
            fields = sorted({str(err["loc"][0]) for err in exc.errors() if err["loc"]})
            raise AppError("settings.invalid", fields=fields) from exc

        new_values = updated.model_dump()
        with self._db.connect() as conn:
            for key in changes:
                conn.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                    "updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')",
                    (key, json.dumps(new_values[key])),
                )
        for listener in self._listeners:
            try:
                listener(current, updated)
            except Exception:
                log.exception("Settings listener failed")
        return updated
