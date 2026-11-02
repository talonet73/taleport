"""Copy text to the Windows clipboard (no browser permission prompts involved)."""

from __future__ import annotations

import ctypes
import sys
import time

_CF_UNICODETEXT = 13
_GMEM_MOVEABLE = 0x0002


def copy_text(text: str) -> bool:
    if sys.platform != "win32":
        return False
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.OpenClipboard.argtypes = [wintypes.HWND]

    data = text.encode("utf-16-le") + b"\x00\x00"
    # The clipboard may be briefly held by another program.
    for _ in range(10):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        return False
    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(_GMEM_MOVEABLE, len(data))
        if not handle:
            return False
        pointer = kernel32.GlobalLock(handle)
        ctypes.memmove(pointer, data, len(data))
        kernel32.GlobalUnlock(handle)
        return bool(user32.SetClipboardData(_CF_UNICODETEXT, handle))
    finally:
        user32.CloseClipboard()
