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

    def to_payload(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "params": self.params}}
