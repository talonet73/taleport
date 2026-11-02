"""Single-instance guard: a named Windows mutex, plus a small file telling a second launch
how to reach the running instance so it can bring its window forward."""

from __future__ import annotations

import ctypes
import json
import logging
import sys
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

_ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = "Local\\TALeport.SingleInstance"


class SingleInstance:
    def __init__(self, name: str = MUTEX_NAME) -> None:
        self._name = name
        self._handle: int | None = None

    def acquire(self) -> bool:
        """True if this is the only running instance."""
        if sys.platform != "win32":
            return True
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        self._handle = kernel32.CreateMutexW(None, False, self._name)
        return ctypes.get_last_error() != _ERROR_ALREADY_EXISTS


def write_instance_file(path: Path, port: int, token: str) -> None:
    path.write_text(json.dumps({"port": port, "token": token}), encoding="utf-8")


def remove_instance_file(path: Path) -> None:
    path.unlink(missing_ok=True)


def focus_running_instance(path: Path) -> bool:
    try:
        info = json.loads(path.read_text(encoding="utf-8"))
        request = urllib.request.Request(
            f"http://127.0.0.1:{int(info['port'])}/api/app/focus",
            method="POST",
            headers={"X-TALeport-Token": info["token"]},
        )
        with urllib.request.urlopen(request, timeout=3):
            return True
    except (OSError, ValueError, KeyError) as exc:
        log.warning("Could not focus the running instance: %s", exc)
        return False
