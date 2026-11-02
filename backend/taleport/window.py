"""Native desktop window (pywebview on Edge WebView2)."""

from __future__ import annotations

from collections.abc import Callable

import webview

from taleport import APP_NAME
from taleport.core.paths import webview_storage_dir

MIN_SIZE = (1280, 720)


class AppWindow:
    def __init__(self, url: str, *, hidden: bool, close_to_tray: Callable[[], bool]) -> None:
        self._close_to_tray = close_to_tray
        self._quitting = False
        self._window = webview.create_window(
            APP_NAME,
            url,
            width=1440,
            height=900,
            min_size=MIN_SIZE,
            background_color="#1E1B4B",
            text_select=True,
            hidden=hidden,
        )
        self._window.events.closing += self._on_closing

    def _on_closing(self) -> bool:
        """Closing the window hides it in the tray (if enabled) instead of quitting."""
        if self._quitting or not self._close_to_tray():
            return True
        self._window.hide()
        return False

    def focus(self) -> None:
        self._window.show()
        self._window.restore()
        # Toggling always-on-top is the reliable way to raise a window on Windows.
        self._window.on_top = True
        self._window.on_top = False

    def quit(self) -> None:
        self._quitting = True
        self._window.destroy()

    def run(self, debug: bool = False) -> None:
        """Blocks until the window is destroyed."""
        webview.start(debug=debug, private_mode=False, storage_path=str(webview_storage_dir()))
