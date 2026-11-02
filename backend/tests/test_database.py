from pathlib import Path

import pytest

from taleport.db.database import Database, migration_files


def test_migrate_creates_schema_and_is_idempotent(tmp_path: Path) -> None:
    db = Database(tmp_path / "a.db")
    expected = len(migration_files())

    assert db.migrate() == expected
    assert db.migrate() == expected
    assert db.schema_version() == expected

    with db.connect() as conn:
        tables = {
            r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert {"settings", "logs"} <= tables


def test_migrate_applies_only_pending_files(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_first.sql").write_text("CREATE TABLE a (id INTEGER);", encoding="utf-8")
    db = Database(tmp_path / "b.db")
    assert db.migrate(migrations) == 1

    (migrations / "0002_second.sql").write_text("CREATE TABLE b (id INTEGER);", encoding="utf-8")
    assert db.migrate(migrations) == 2


def test_failed_migration_is_rolled_back(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_ok.sql").write_text("CREATE TABLE a (id INTEGER);", encoding="utf-8")
    (migrations / "0002_broken.sql").write_text(
        "CREATE TABLE b (id INTEGER);\nTHIS IS NOT SQL;", encoding="utf-8"
    )
    db = Database(tmp_path / "c.db")

    with pytest.raises(Exception):  # noqa: B017 - sqlite3 raises OperationalError
        db.migrate(migrations)

    assert db.schema_version() == 1
    with db.connect() as conn:
        tables = {
            r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert "b" not in tables


def test_migration_numbering_must_be_contiguous(tmp_path: Path) -> None:
    (tmp_path / "0001_a.sql").write_text("", encoding="utf-8")
    (tmp_path / "0003_c.sql").write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        migration_files(tmp_path)
