"""User-facing errors.

The backend never sends text to the UI: it sends a stable `code` (an i18n key under `errors.`)
plus optional `params`, and the UI translates it.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    def __init__(self, code: str, status: int = 400, **params: Any) -> None:
        super().__init__(code)
        self.code = code
        self.status = status
        self.params = params

    @classmethod
    def from_provider(cls, exc: Exception, status: int = 502) -> AppError:
        """An AI provider failure as a user-facing error. Provider params never clash with
        the HTTP status of the response (a provider's own `status` is renamed)."""
        params = dict(getattr(exc, "params", {}))
        if "status" in params:
            params["http_status"] = params.pop("status")
        return cls(getattr(exc, "code", "ai.provider_error"), status=status, **params)

    def to_payload(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "params": self.params}}
