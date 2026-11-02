import pytest

from taleport.core.errors import AppError
from taleport.core.secrets import SECRET_NAMES, SecretStore


def test_set_get_delete_roundtrip() -> None:
    store = SecretStore()
    assert store.get("youtube") is None

    store.set("youtube", "  abc123  ")
    assert store.get("youtube") == "abc123"
    assert store.status()["youtube"] is True

    store.delete("youtube")
    store.delete("youtube")  # deleting a missing secret is not an error
    assert store.status()["youtube"] is False


def test_status_lists_every_known_secret() -> None:
    assert set(SecretStore().status()) == set(SECRET_NAMES)


def test_unknown_name_and_empty_value_are_rejected() -> None:
    store = SecretStore()
    with pytest.raises(AppError) as info:
        store.set("github", "x")
    assert info.value.code == "secrets.unknown"
    with pytest.raises(AppError) as info:
        store.set("openai", "   ")
    assert info.value.code == "secrets.empty"


def test_values_are_stored_under_the_app_service(isolated_env) -> None:
    SecretStore().set("openai", "sk-test")
    assert isolated_env.store == {("TALeport", "openai"): "sk-test"}
