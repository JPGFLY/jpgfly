"""Privacy-preserving local human-input sentinel for JPGFLY.

On Windows this reads only the timestamp-like tick count exposed by
GetLastInputInfo. It never records keys, buttons, pointer coordinates, text,
window titles, or input content.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from typing import Any


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwTime", wintypes.DWORD),
    ]


def local_input_snapshot() -> dict[str, Any]:
    if sys.platform != "win32":
        return {
            "supported": False,
            "source": "WINDOWS_GETLASTINPUTINFO",
            "last_input_tick_ms": None,
            "records_content": False,
        }

    info = _LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(_LASTINPUTINFO)
    try:
        ok = ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
    except Exception:
        ok = 0

    if not ok:
        return {
            "supported": False,
            "source": "WINDOWS_GETLASTINPUTINFO",
            "last_input_tick_ms": None,
            "records_content": False,
        }

    return {
        "supported": True,
        "source": "WINDOWS_GETLASTINPUTINFO",
        "last_input_tick_ms": int(info.dwTime),
        "records_content": False,
    }
