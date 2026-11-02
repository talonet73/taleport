"""Files the app writes for the user (PDF reports, backups, shared topics, error logs).

All of them go to `%LOCALAPPDATA%\\TALeport\\exports\\` and are opened with the default
Windows program: the app window never handles downloads. Names coming back from the page
are checked so they can only point at a plain file in that folder.
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from taleport.core.errors import AppError
from taleport.core.paths import exports_dir

EXTENSIONS = (".pdf", ".json", ".txt")
_SAFE_NAME = re.compile(r"^[\w\-. ]+\.(pdf|json|txt)$")
RECENT_FILES = 20


def stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def safe_label(text: str, max_length: int = 40) -> str:
    """A file-name friendly version of a user label ("Moda & stile" → "Moda_stile")."""
    label = re.sub(r"[^\w\-]+", "_", text, flags=re.UNICODE).strip("_")
    return label[:max_length] or "file"


def save(name: str, data: bytes) -> dict[str, Any]:
    path = exports_dir() / name
    path.write_bytes(data)
    return {"name": name, "size": len(data), "path": str(path)}


def file_path(name: str) -> Path:
    if not _SAFE_NAME.match(name) or ".." in name:
        raise AppError("exports.not_found", status=404)
    path = exports_dir() / name
    if not path.is_file():
        raise AppError("exports.not_found", status=404)
    return path


def open_file(name: str, *, folder: bool = False) -> None:
    path = file_path(name)
    os.startfile(path.parent if folder else path)  # type: ignore[attr-defined]  # Windows only


def recent(suffix: str | None = None, limit: int = RECENT_FILES) -> list[dict[str, Any]]:
    files = [
        f
        for f in exports_dir().iterdir()
        if f.is_file() and f.suffix in EXTENSIONS and (suffix is None or f.suffix == suffix)
    ]
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return [
        {
            "name": f.name,
            "size": f.stat().st_size,
            "modified": datetime.fromtimestamp(f.stat().st_mtime).astimezone().isoformat(),
        }
        for f in files[:limit]
    ]
