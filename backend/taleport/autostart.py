"""'Start with Windows' via the per-user Run registry key (no admin rights needed)."""

from __future__ import annotations

import contextlib
import logging
import sys
from pathlib import Path

from taleport import APP_NAME

log = logging.getLogger(__name__)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def launch_command() -> str:
    """Command line Windows runs at sign-in: the app, started minimized to the tray."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'
    # Development: prefer pythonw.exe so no console window appears.
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    return f'"{pythonw if pythonw.exists() else exe}" -m taleport --minimized'


def set_autostart(enabled: bool) -> None:
    if sys.platform != "win32":
        return
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, launch_command())
        else:
            with contextlib.suppress(FileNotFoundError):
                winreg.DeleteValue(key, APP_NAME)
    log.info("Start with Windows %s", "enabled" if enabled else "disabled")


def is_autostart_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False
