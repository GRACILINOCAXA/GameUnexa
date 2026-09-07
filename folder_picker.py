"""Native directory selection for the desktop application."""

from __future__ import annotations

import ctypes
import os


def select_folder() -> str:
    """Return a selected directory, or an empty string when cancelled."""
    if os.name != 'nt':
        return ''

    try:
        from ctypes import wintypes

        class BROWSEINFO(ctypes.Structure):
            _fields_ = [
                ('hwndOwner', wintypes.HWND),
                ('pidlRoot', wintypes.LPCITEMIDLIST),
                ('pszDisplayName', wintypes.LPWSTR),
                ('lpszTitle', wintypes.LPCWSTR),
                ('ulFlags', wintypes.UINT),
                ('lpfn', ctypes.c_void_p),
                ('lParam', wintypes.LPARAM),
                ('iImage', ctypes.c_int),
            ]

        shell32 = ctypes.windll.shell32
        ole32 = ctypes.windll.ole32
        shell32.SHBrowseForFolderW.argtypes = [ctypes.POINTER(BROWSEINFO)]
        shell32.SHBrowseForFolderW.restype = ctypes.c_void_p
        shell32.SHGetPathFromIDListW.argtypes = [ctypes.c_void_p, wintypes.LPWSTR]
        shell32.SHGetPathFromIDListW.restype = wintypes.BOOL
        ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        ole32.CoTaskMemFree.restype = None
        info = BROWSEINFO(
            lpszTitle='Selecionar pasta',
            ulFlags=0x0001 | 0x0040,
        )
        item = shell32.SHBrowseForFolderW(ctypes.byref(info))
        if not item:
            return ''
        try:
            path_buffer = ctypes.create_unicode_buffer(32768)
            if shell32.SHGetPathFromIDListW(item, path_buffer):
                return path_buffer.value.strip()
            return ''
        finally:
            ole32.CoTaskMemFree(item)
        return ''
    except Exception:
        return ''