"""Clean-up, backup and import, single-topic sharing, update check, error log."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from taleport.api.context import AppContext, build_context
from taleport.collectors.http import HttpClient
from taleport.core.errors import AppError
from taleport.core.maintenance import cleanup
from taleport.core.paths import exports_dir
from taleport.db.database import Database
from taleport.reports.service import CustomReport
from taleport.updates.service import UpdateService, parse_version, read_release
from tests.conftest import TEST_TOKEN, topic_payload

NOW = datetime(2026, 11, 2, 12, tzinfo=UTC)
FMT = "%Y-%m-%dT%H:%M:%S.000Z"


def _item(conn, url: str, last_seen: datetime, topic_id: int) -> int:
    item_id = conn.execute(
        "INSERT INTO items (source, url, canonical_url, title, title_key, last_seen_at) "
        "VALUES ('news', ?, ?, 't', 't', ?)",
        (url, url, last_seen.strftime(FMT)),
    ).lastrowid
    conn.execute(
        "INSERT INTO item_topics (item_id, topic_id, linked_at) VALUES (?, ?, ?)",
        (item_id, topic_id, last_seen.strftime(FMT)),
    )
    return item_id


# -- clean-up --------------------------------------------------------------------------


def test_cleanup_removes_only_old_data(ctx: AppContext) -> None:
    topic = ctx.topics.create(topic_payload()).id
    with ctx.db.connect() as conn:
        _item(conn, "https://x/old", NOW - timedelta(days=200), topic)
        _item(conn, "https://x/new", NOW - timedelta(days=20), topic)
        conn.execute(
            "INSERT INTO logs (created_at, level, source, code) VALUES (?, 'info', 's', 'a'), "
            "(?, 'info', 's', 'b')",
            ((NOW - timedelta(days=120)).strftime(FMT), NOW.strftime(FMT)),
        )
        conn.execute(
            "INSERT INTO notifications (created_at, kind, read) VALUES (?, 'x', 1), (?, 'x', 0)",
            ((NOW - timedelta(days=120)).strftime(FMT),) * 2,
        )
    assert cleanup(ctx.db, 6, NOW) == {"items": 1, "logs": 1, "notifications": 1}
    with ctx.db.connect() as conn:
        assert [r[0] for r in conn.execute("SELECT url FROM items")] == ["https://x/new"]
        assert conn.execute("SELECT COUNT(*) FROM item_topics").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0] == 1  # unread
    assert cleanup(ctx.db, 0, NOW + timedelta(days=3650))["items"] == 0  # 0 = keep forever


# -- backup ----------------------------------------------------------------------------


def test_backup_round_trip_without_secrets(ctx: AppContext, tmp_path) -> None:
    ctx.secrets.set("openai", "sk-secret-value")
    ctx.settings.update({"language": "en", "scan_time": "08:15", "first_run_completed": True,
                         "start_with_windows": True, "report_cover_name": "Agenzia"})  # fmt: skip
    t1 = ctx.topics.create(topic_payload(name="Moda")).id
    ctx.topics.create(topic_payload(name="Food"))
    ctx.reports.save_template(
        "Mensile", CustomReport(sections=["keywords"], filters={"topics": [t1]})
    )
    saved = ctx.backup.export_all()
    assert saved["name"].startswith("TALeport_backup_") and saved["topics"] == 2
    text = (exports_dir() / saved["name"]).read_text(encoding="utf-8")
    data = json.loads(text)
    assert "sk-secret-value" not in text
    assert "first_run_completed" not in data["settings"]
    assert "start_with_windows" not in data["settings"]
    assert data["report_templates"][0]["params"]["filters"]["topic_names"] == ["Moda"]

    # Another PC: a fresh database already holding a topic called "Moda".
    other = build_context(
        Database(tmp_path / "other.db"), TEST_TOKEN, collectors_factory=lambda: []
    )
    other.db.migrate()
    other.topics.create(topic_payload(name="Moda"))
    assert other.backup.preview(text) == {
        "format": "taleport-backup", "app_version": data["app_version"],
        "created_at": data["created_at"], "topics": ["Moda", "Food"], "has_settings": True,
        "templates": 1,
    }  # fmt: skip
    result = other.backup.import_file(text)
    assert result == {"topics": ["Moda (2)", "Food"], "skipped": [], "settings": True,
                      "templates": 1}  # fmt: skip
    restored = other.settings.get()
    assert restored.language == "en" and restored.scan_time == "08:15"
    assert restored.first_run_completed is False and restored.start_with_windows is False
    template = other.reports.templates()[0]
    imported_moda = next(t.id for t in other.topics.list() if t.name == "Moda (2)")
    assert template["params"]["filters"]["topics"] == [imported_moda]


def test_reimporting_adds_no_identical_templates(ctx: AppContext) -> None:
    ctx.reports.save_template("Settimanale", CustomReport(sections=["summary"]))
    text = (exports_dir() / ctx.backup.export_all()["name"]).read_text(encoding="utf-8")
    assert ctx.backup.import_file(text, settings=False)["templates"] == 0
    assert len(ctx.reports.templates()) == 1


def test_import_rejects_bad_files_and_respects_the_limit(ctx: AppContext) -> None:
    for text, code in (
        ("not json", "backup.invalid_file"),
        ('{"format": "something-else"}', "backup.invalid_file"),
        ('{"format": "taleport-backup", "version": 99}', "backup.newer_version"),
    ):
        with pytest.raises(AppError) as info:
            ctx.backup.import_file(text)
        assert info.value.code == code
    for i in range(9):
        ctx.topics.create(topic_payload(name=f"T{i}"))
    payload = {"format": "taleport-backup", "version": 1, "topics": [
        topic_payload(name="Nuovo"), topic_payload(name="Troppi"), {"name": "rotto"},
    ]}  # fmt: skip
    result = ctx.backup.import_file(json.dumps(payload), settings=False)
    assert result["topics"] == ["Nuovo"]
    assert result["skipped"] == [{"name": "Troppi", "reason": "limit"},
                                 {"name": "rotto", "reason": "limit"}]  # fmt: skip


def test_share_a_single_topic(ctx: AppContext) -> None:
    topic = ctx.topics.create(topic_payload(name="Moda & stile"))
    saved = ctx.backup.export_topic(topic.id)
    assert saved["name"].startswith("TALeport_argomento_Moda_stile_")
    text = (exports_dir() / saved["name"]).read_text(encoding="utf-8")
    assert json.loads(text)["topic"]["keywords"]["it"] == ["intelligenza artificiale"]
    assert ctx.backup.import_file(text)["topics"] == ["Moda & stile (2)"]
    broken = json.loads(text)
    broken["topic"]["editions"] = ["xx-YY"]
    assert ctx.backup.import_file(json.dumps(broken))["skipped"][0]["reason"] == "invalid"


# -- updates ---------------------------------------------------------------------------


def test_versions_and_release_formats() -> None:
    assert parse_version("v1.2.10") == (1, 2, 10) and parse_version("0.2") == (0, 2, 0)
    assert parse_version("1.0.0-beta.2") == (1, 0, 0)
    asset = "https://github.com/o/taleport/releases/download/a.exe"
    github = {
        "tag_name": "v0.2.0",
        "html_url": "https://github.com/o/taleport/releases/v0.2.0",
        "body": "Novità",
        "assets": [{"name": "Setup-TALeport.exe", "browser_download_url": asset}],
    }
    release = read_release(github)
    assert release["version"] == "0.2.0" and release["installer_url"].endswith("a.exe")
    plain = read_release({"version": "0.3.0", "url": "https://example.com/taleport"})
    assert plain == {"version": "0.3.0", "url": "https://example.com/taleport",
                     "installer_url": None, "notes": ""}  # fmt: skip
    with pytest.raises(ValueError):
        read_release({"version": "1.0", "url": "http://insecure"})


def _updates(ctx: AppContext, handler) -> UpdateService:
    http = HttpClient(transport=httpx.MockTransport(handler), sleep=lambda _s: None)
    return UpdateService(ctx.db, ctx.settings, http, ctx.notifications, current="0.1.0")


def test_update_check(ctx: AppContext) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "missing" in str(request.url):
            return httpx.Response(404)
        return httpx.Response(200, json={"version": "0.2.0", "url": "https://example.com/r"})

    service = _updates(ctx, handler)
    with pytest.raises(AppError) as info:
        service.check()
    assert info.value.code == "updates.not_configured"
    ctx.settings.update({"update_url": "https://example.com/latest.json"})
    result = service.check()
    assert result["available"] and result["latest"]["version"] == "0.2.0"
    notes = ctx.notifications.list()["rows"]
    assert notes[0]["kind"] == "update_available" and notes[0]["params"]["version"] == "0.2.0"
    service.check_if_due(datetime.now(UTC) + timedelta(hours=2))  # checked less than a day ago
    assert len(calls) == 1
    service.current = "0.2.0"
    assert service.check()["available"] is False
    ctx.settings.update({"update_url": "https://example.com/missing.json"})
    with pytest.raises(AppError) as info:
        service.check()
    assert info.value.code == "updates.no_release"
    with pytest.raises(AppError):
        ctx.settings.update({"update_url": "http://not-https.example.com"})


# -- API -------------------------------------------------------------------------------


def test_system_api(client: TestClient, ctx: AppContext) -> None:
    ctx.logs.add("error", "collector.reddit", "source.http", {"status": 403}, "Traceback: boom")
    ctx.logs.add("info", "scan", "scan.done")
    logs = client.get("/api/logs?level=error").json()
    assert logs["counts"] == {"info": 1, "warning": 0, "error": 1}
    assert [r["code"] for r in logs["rows"]] == ["source.http"]
    exported = client.post("/api/logs/export").json()
    text = (exports_dir() / exported["name"]).read_text(encoding="utf-8")
    assert "Traceback: boom" in text and "version: " in text
    assert client.delete("/api/logs").status_code == 204
    assert client.get("/api/logs").json()["rows"] == []

    backup = client.post("/api/backup/export").json()
    assert any(f["name"] == backup["name"] for f in client.get("/api/exports").json())
    assert client.get("/api/exports?suffix=.txt").json()[0]["name"] == exported["name"]
    preview = client.post("/api/backup/preview", json={"text": "{}"}).json()
    assert preview["error"]["code"] == "backup.invalid_file"

    opened = []
    ctx.open_url = opened.append
    assert client.post("/api/updates/open").json()["error"]["code"] == "updates.not_checked"
    assert client.get("/api/updates").json()["configured"] is False
    assert client.post("/api/maintenance/cleanup").json() == {
        "items": 0, "logs": 0, "notifications": 0,
    }  # fmt: skip
    assert client.post("/api/exports/open", json={"name": "../x.pdf"}).status_code == 404
