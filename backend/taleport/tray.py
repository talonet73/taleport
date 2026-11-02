"""System tray icon: keeps TALeport (and its scheduled scans) alive with the window closed."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path

import pystray
from PIL import Image

from taleport.core.i18n import tr

log = logging.getLogger(__name__)


class Tray:
    def __init__(
        self,
        icon_path: Path,
        language: Callable[[], str],
        on_open: Callable[[], None],
        on_scan: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        def label(key: str) -> Callable[[pystray.MenuItem], str]:
            return lambda _item: tr(language(), key)

        menu = pystray.Menu(
            pystray.MenuItem(label("tray.open"), lambda: on_open(), default=True),
            pystray.MenuItem(label("tray.scan_now"), lambda: on_scan()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(label("tray.quit"), lambda: on_quit()),
        )
        self._icon = pystray.Icon(
            "TALeport", Image.open(icon_path), tr(language(), "tray.tooltip"), menu
        )
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._icon.run, name="tray", daemon=True)
        self._thread.start()

    def refresh(self) -> None:
        """Re-read menu labels (after a language change)."""
        self._icon.update_menu()

    def stop(self) -> None:
        try:
            self._icon.stop()
        except Exception:  # the icon may never have been shown
            log.debug("Tray stop failed", exc_info=True)
