from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import keyring
import pytest
from fastapi.testclient import TestClient
from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError

from taleport.api.app import create_app
from taleport.api.context import AppContext, build_context
from taleport.collectors.base import CollectedItem
from taleport.db.database import Database
from taleport.topics.models import Topic

TEST_TOKEN = "test-token"
FIXTURES = Path(__file__).parent / "fixtures"


def topic_payload(**overrides: object) -> dict:
    data = {
        "name": "AI marketing",
        "editions": ["it-IT", "en-US"],
        "keywords": {"it": ["intelligenza artificiale"], "en": ["artificial intelligence"]},
        "exclude": ["crypto"],
        "hashtags": ["#AI"],
    }
    data.update(overrides)
    return data


class FakeCollector:
    """Returns canned items per topic name, or raises a given exception."""

    def __init__(self, source: str, items: list[CollectedItem] | None = None, error=None):
        self.source = source
        self.items = items or []
        self.error = error
        self.calls: list[int] = []

    def collect(self, topic: Topic) -> list[CollectedItem]:
        self.calls.append(topic.id)
        if self.error:
            raise self.error
        return list(self.items)


class MemoryKeyring(KeyringBackend):
    priority = 1  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        if (service, username) not in self.store:
            raise PasswordDeleteError(username)
        del self.store[(service, username)]


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[MemoryKeyring]:
    """Never touch the real data folder or the real Windows Credential Manager."""
    monkeypatch.setenv("TALEPORT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("taleport.core.clipboard.copy_text", lambda _text: True)
    previous = keyring.get_keyring()
    backend = MemoryKeyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "test.db")
    database.migrate()
    return database


@pytest.fixture
def collectors() -> list[FakeCollector]:
    """The collectors used by `ctx` scans; tests may append or replace entries."""
    return []


@pytest.fixture
def ctx(db: Database, collectors: list[FakeCollector]) -> AppContext:
    return build_context(db, TEST_TOKEN, collectors_factory=lambda: list(collectors))


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>TALeport</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
    return dist


@pytest.fixture
def client(ctx: AppContext, static_dir: Path) -> Iterator[TestClient]:
    app = create_app(ctx, static_dir=static_dir)
    with TestClient(app, base_url="http://127.0.0.1") as test_client:
        test_client.headers["X-TALeport-Token"] = TEST_TOKEN
        yield test_client
