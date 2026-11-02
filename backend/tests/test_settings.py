import pytest

from taleport.core.errors import AppError
from taleport.core.settings import AppSettings, SettingsStore
from taleport.db.database import Database


def test_defaults_when_nothing_stored(db: Database) -> None:
    assert SettingsStore(db).get() == AppSettings()


def test_update_persists_only_changed_keys(db: Database) -> None:
    store = SettingsStore(db)
    updated = store.update({"language": "es", "theme": "light"})

    assert updated.language == "es"
    assert SettingsStore(db).get().theme == "light"
    with db.connect() as conn:
        keys = {r["key"] for r in conn.execute("SELECT key FROM settings")}
    assert keys == {"language", "theme"}


@pytest.mark.parametrize(
    "changes",
    [{"language": "fr"}, {"scan_time": "25:00"}, {"theme": "blue"}, {"unknown_key": 1}],
)
def test_invalid_values_are_rejected(db: Database, changes: dict) -> None:
    with pytest.raises(AppError) as info:
        SettingsStore(db).update(changes)
    assert info.value.code == "settings.invalid"
    assert SettingsStore(db).get() == AppSettings()


def test_corrupt_stored_value_falls_back_to_default(db: Database) -> None:
    with db.connect() as conn:
        conn.execute("INSERT INTO settings (key, value) VALUES ('theme', '\"neon\"')")
        conn.execute("INSERT INTO settings (key, value) VALUES ('language', '\"en\"')")
    settings = SettingsStore(db).get()
    assert settings.theme == "dark"
    assert settings.language == "en"
