"""Is Fortnite running?

Lists process names with the Toolhelp snapshot API — the same call Task Manager
uses. It only reads the list of running programs: nothing is opened, injected
or read from the game process.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes as wt

# FortniteClient-Win64-Shipping.exe is the game itself; the _BE / _EAC variants
# are its anti-cheat bootstrappers and start at the same moment.
DEFAULT_PREFIX = "fortniteclient-win64-shipping"

TH32CS_SNAPPROCESS = 0x00000002
MAX_PATH = 260


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wt.DWORD),
        ("szExeFile", ctypes.c_wchar * MAX_PATH),
    ]


class GameWatcher:
    def __init__(self, prefix: str = DEFAULT_PREFIX) -> None:
        self.prefix = (prefix or DEFAULT_PREFIX).lower()
        self._k32 = None
        if sys.platform == "win32":
            try:
                k32 = ctypes.WinDLL("kernel32", use_last_error=True)
                k32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
                k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
                k32.Process32FirstW.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
                k32.Process32FirstW.restype = wt.BOOL
                k32.Process32NextW.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
                k32.Process32NextW.restype = wt.BOOL
                k32.CloseHandle.argtypes = [wt.HANDLE]
                k32.CloseHandle.restype = wt.BOOL
                self._k32 = k32
            except Exception:
                self._k32 = None

    @property
    def available(self) -> bool:
        return self._k32 is not None

    def is_running(self) -> bool:
        k32 = self._k32
        if k32 is None:
            return False
        snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if not snap or snap == wt.HANDLE(-1).value:
            return False
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            ok = k32.Process32FirstW(snap, ctypes.byref(entry))
            while ok:
                if entry.szExeFile.lower().startswith(self.prefix):
                    return True
                ok = k32.Process32NextW(snap, ctypes.byref(entry))
            return False
        finally:
            k32.CloseHandle(snap)
