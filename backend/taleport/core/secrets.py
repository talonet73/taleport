"""API keys and other secrets, stored in the Windows Credential Manager through `keyring`.

Secret values never reach the database, files, backups or the UI: the API only reports
whether each secret is set.
"""

from __future__ import annotations

import logging
from typing import Literal, get_args

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

from taleport import APP_NAME
from taleport.core.errors import AppError

log = logging.getLogger(__name__)

SecretName = Literal[
    "anthropic",
    "openai",
    "xai",
    "perplexity",
    "gemini",
    "youtube",
]
SECRET_NAMES: tuple[str, ...] = get_args(SecretName)


class SecretStore:
    def __init__(self, service: str = APP_NAME) -> None:
        self._service = service

    @staticmethod
    def _check_name(name: str) -> None:
        if name not in SECRET_NAMES:
            raise AppError("secrets.unknown", status=404, name=name)

    def get(self, name: str) -> str | None:
        self._check_name(name)
        try:
            return keyring.get_password(self._service, name)
        except KeyringError as exc:
            log.warning("Credential store unavailable: %s", exc)
            raise AppError("secrets.unavailable", status=503) from exc

    def set(self, name: str, value: str) -> None:
        self._check_name(name)
        value = value.strip()
        if not value:
            raise AppError("secrets.empty")
        try:
            keyring.set_password(self._service, name, value)
        except KeyringError as exc:
            log.warning("Credential store unavailable: %s", exc)
            raise AppError("secrets.unavailable", status=503) from exc

    def delete(self, name: str) -> None:
        self._check_name(name)
        try:
            keyring.delete_password(self._service, name)
        except PasswordDeleteError:
            pass  # already absent
        except KeyringError as exc:
            log.warning("Credential store unavailable: %s", exc)
            raise AppError("secrets.unavailable", status=503) from exc

    def status(self) -> dict[str, bool]:
        return {name: bool(self.get(name)) for name in SECRET_NAMES}
