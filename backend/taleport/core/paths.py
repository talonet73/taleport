"""Filesystem locations used by the app."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from taleport import APP_NAME


def data_dir() -> Path:
    """Per-user data folder (%LOCALAPPDATA%\\TALeport). TALEPORT_DATA_DIR overrides it (tests)."""
    override = os.environ.get("TALEPORT_DATA_DIR")
    if override:
        base = Path(override)
    else:
        local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        base = Path(local) / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def _subdir(name: str) -> Path:
    path = data_dir() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "taleport.db"


def logs_dir() -> Path:
    return _subdir("logs")


def webview_storage_dir() -> Path:
    return _subdir("webview")


def instance_file() -> Path:
    """Port and session token of the running instance, used to focus it from a second launch."""
    return data_dir() / "instance.json"


def bundle_root() -> Path:
    """Root of bundled resources: PyInstaller's extraction dir when frozen, else the repo root."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[3]


def frontend_dist() -> Path:
    root = bundle_root()
    return root / "frontend" if getattr(sys, "frozen", False) else root / "frontend" / "dist"
