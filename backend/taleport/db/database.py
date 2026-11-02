"""SQLite access and versioned migrations.

Migrations are plain SQL files named `NNNN_description.sql` in `migrations/`. The applied
version is stored in `PRAGMA user_version`. Released migrations are never edited: schema
changes always go in a new file.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_MIGRATION_NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


def migration_files(directory: Path = MIGRATIONS_DIR) -> list[tuple[int, Path]]:
    found: list[tuple[int, Path]] = []
    for path in directory.glob("*.sql"):
        match = _MIGRATION_NAME.match(path.name)
        if not match:
            raise ValueError(f"Invalid migration file name: {path.name}")
        found.append((int(match.group(1)), path))
    found.sort()
    versions = [version for version, _ in found]
    if versions != list(range(1, len(versions) + 1)):
        raise ValueError(f"Migrations must be numbered 0001, 0002, ... without gaps: {versions}")
    return found


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """A short-lived connection; commits on success, rolls back on error."""
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def schema_version(self) -> int:
        with self.connect() as conn:
            return conn.execute("PRAGMA user_version").fetchone()[0]

    def migrate(self, directory: Path = MIGRATIONS_DIR) -> int:
        """Apply pending migrations, each in its own transaction. Returns the new version."""
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            current = conn.execute("PRAGMA user_version").fetchone()[0]
            for version, path in migration_files(directory):
                if version <= current:
                    continue
                sql = path.read_text(encoding="utf-8")
                conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {version};\nCOMMIT;")
                current = version
        return current
