"""Backup and sharing in a single JSON file.

- Full backup: settings, topics and custom report templates. API keys are never included
  (they live in Windows Credential Manager), nor collected items or drafts.
- Single topic: a file a colleague can import into their own TALeport.
Imports are validated with the same models as the editor; nothing is overwritten: topics
whose name already exists get a numbered name, and the 10-topic limit is respected.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from taleport import __version__
from taleport.core import exports
from taleport.core.errors import AppError
from taleport.core.settings import AppSettings, SettingsStore
from taleport.db.database import Database
from taleport.reports.service import CustomReport, ReportService
from taleport.topics.models import MAX_TOPICS, TopicData
from taleport.topics.service import TopicStore

BACKUP_FORMAT = "taleport-backup"
TOPIC_FORMAT = "taleport-topic"
VERSION = 1
MAX_IMPORT_BYTES = 2 * 1024 * 1024
# Machine-specific or one-off: never restored on another PC.
_NOT_RESTORED = {"first_run_completed", "start_with_windows"}


def _topic_data(topic: Any) -> dict[str, Any]:
    return TopicData.model_validate(
        topic.model_dump(include=set(TopicData.model_fields))
    ).model_dump(mode="json")


class BackupService:
    def __init__(
        self, db: Database, settings: SettingsStore, topics: TopicStore, reports: ReportService
    ) -> None:
        self._db = db
        self._settings = settings
        self._topics = topics
        self._reports = reports

    # -- export --------------------------------------------------------------------------

    def _envelope(self, kind: str, **content: Any) -> dict[str, Any]:
        return {
            "format": kind,
            "version": VERSION,
            "app_version": __version__,
            "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
            **content,
        }

    def export_all(self) -> dict[str, Any]:
        topics = self._topics.list()
        names = {t.id: t.name for t in topics}
        templates = []
        for template in self._reports.templates():
            params = dict(template["params"])
            filters = dict(params.get("filters") or {})
            # Topic ids differ between PCs: templates refer to topics by name.
            filters["topic_names"] = [
                names[i] for i in filters.pop("topics", None) or [] if i in names
            ]
            params["filters"] = filters
            templates.append({"name": template["name"], "params": params})
        data = self._envelope(
            BACKUP_FORMAT,
            settings=self._settings.get().model_dump(mode="json", exclude=_NOT_RESTORED),
            topics=[_topic_data(t) for t in topics],
            report_templates=templates,
        )
        name = f"TALeport_backup_{exports.stamp()}.json"
        return {**self._write(name, data), "topics": len(topics), "templates": len(templates)}

    def export_topic(self, topic_id: int) -> dict[str, Any]:
        topic = self._topics.get(topic_id)
        data = self._envelope(TOPIC_FORMAT, topic=_topic_data(topic))
        name = f"TALeport_argomento_{exports.safe_label(topic.name)}_{exports.stamp()}.json"
        return self._write(name, data)

    @staticmethod
    def _write(name: str, data: dict[str, Any]) -> dict[str, Any]:
        text = json.dumps(data, ensure_ascii=False, indent=2)
        return exports.save(name, text.encode("utf-8"))

    # -- import --------------------------------------------------------------------------

    @staticmethod
    def _parse(text: str) -> dict[str, Any]:
        if len(text.encode("utf-8")) > MAX_IMPORT_BYTES:
            raise AppError("backup.too_large", max_mb=MAX_IMPORT_BYTES // (1024 * 1024))
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AppError("backup.invalid_file") from exc
        if not isinstance(data, dict) or data.get("format") not in (BACKUP_FORMAT, TOPIC_FORMAT):
            raise AppError("backup.invalid_file")
        if int(data.get("version", 0)) > VERSION:
            raise AppError("backup.newer_version", version=str(data.get("app_version", "")))
        return data

    def preview(self, text: str) -> dict[str, Any]:
        """What an import would bring in, shown before the user confirms."""
        data = self._parse(text)
        topics = [data["topic"]] if data["format"] == TOPIC_FORMAT else data.get("topics", [])
        return {
            "format": data["format"],
            "app_version": data.get("app_version"),
            "created_at": data.get("created_at"),
            "topics": [t.get("name", "") for t in topics if isinstance(t, dict)],
            "has_settings": data["format"] == BACKUP_FORMAT and bool(data.get("settings")),
            "templates": len(data.get("report_templates", []) or []),
        }

    def import_file(self, text: str, *, settings: bool = True) -> dict[str, Any]:
        data = self._parse(text)
        result: dict[str, Any] = {"topics": [], "skipped": [], "settings": False, "templates": 0}
        topics = [data["topic"]] if data["format"] == TOPIC_FORMAT else data.get("topics", [])
        created = {t.name: t.id for t in self._topics.list()}
        for raw in topics:
            if len(created) >= MAX_TOPICS:
                result["skipped"].append({"name": raw.get("name", ""), "reason": "limit"})
                continue
            try:
                topic = TopicData.model_validate(raw)
            except (ValidationError, TypeError):
                result["skipped"].append({"name": str(raw.get("name", "")), "reason": "invalid"})
                continue
            payload = topic.model_dump(mode="json")
            payload["name"] = self._free_name(topic.name, set(created))
            saved = self._topics.create(payload)
            created[topic.name] = saved.id  # templates refer to the original name
            created[saved.name] = saved.id
            result["topics"].append(saved.name)
        if data["format"] == BACKUP_FORMAT:
            if settings and isinstance(data.get("settings"), dict):
                result["settings"] = self._restore_settings(data["settings"])
            result["templates"] = self._restore_templates(
                data.get("report_templates") or [], created
            )
        return result

    @staticmethod
    def _free_name(name: str, taken: set[str]) -> str:
        if name not in taken:
            return name
        n = 2
        while f"{name} ({n})" in taken:
            n += 1
        return f"{name} ({n})"[:80]

    def _restore_settings(self, stored: dict[str, Any]) -> bool:
        # Field by field: one value from an older or newer version must not block the rest.
        valid: dict[str, Any] = {}
        for key, value in stored.items():
            if key in _NOT_RESTORED or key not in AppSettings.model_fields:
                continue
            try:
                AppSettings.model_validate({key: value})
            except ValidationError:
                continue
            valid[key] = value
        if valid:
            self._settings.update(valid)
        return bool(valid)

    def _restore_templates(self, templates: list[Any], topic_ids: dict[str, int]) -> int:
        existing = {
            (t["name"], json.dumps(t["params"], sort_keys=True)) for t in self._reports.templates()
        }
        count = 0
        for template in templates:
            try:
                params = dict(template["params"])
                filters = dict(params.get("filters") or {})
                names = filters.pop("topic_names", None) or []
                ids = [topic_ids[n] for n in names if n in topic_ids]
                filters["topics"] = ids or None
                params["filters"] = filters
                report = CustomReport.model_validate(params)
                key = (
                    str(template["name"]),
                    json.dumps(report.model_dump(mode="json"), sort_keys=True),
                )
                if key in existing:  # importing the same backup twice adds nothing
                    continue
                self._reports.save_template(key[0], report)
                existing.add(key)
                count += 1
            except (AppError, KeyError, TypeError, ValidationError):
                continue
        return count
