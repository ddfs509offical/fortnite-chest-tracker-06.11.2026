"""Global key watcher: F1 = on/off, F2 = +1 chest, F3 = -1 chest, Numpad + = move the island.

No hooks. The tracker polls ``GetAsyncKeyState`` from the Qt thread (~30 Hz).
Polling only *reads* the keyboard state: nothing sits in the input path, so the
tracker can never delay, swallow or break keys for Windows, Fortnite or Easy
Anti-Cheat, and Fortnite keeps receiving F1 as usual.

(The previous version used a WH_KEYBOARD_LL hook. A low-level hook is called
synchronously for *every* keystroke in the whole system; if the hook thread is
late — game at full load, Python GIL busy, antivirus/EAC scanning — Windows
waits for it on each key, and the keyboard feels dead. Also, CallNextHookEx was
called without argtypes, which overflows on 64-bit Python and broke the chain.)
"""

from __future__ import annotations

import sys

VK_F1 = 0x70
VK_NUMPAD_ADD = 0x6B
VK_F2 = 0x71          # +1 chest
VK_F3 = 0x72          # -1 chest (undo)

_WATCHED = (VK_F1, VK_F2, VK_F3, VK_NUMPAD_ADD)


class KeyHook:
    """Edge-triggered key poller. Call :meth:`poll` regularly from one thread."""

    def __init__(self, on_event) -> None:
        self._on_event = on_event
        self._down: dict[int, bool] = {vk: False for vk in _WATCHED}
        self._get_state = None
        self.active = False

    def start(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            import ctypes

            fn = ctypes.windll.user32.GetAsyncKeyState
            fn.argtypes = [ctypes.c_int]
            fn.restype = ctypes.c_short
            self._get_state = fn
        except Exception:
            return False
        # Treat keys that are already held at start-up as "down", so launching
        # the tracker while F1 is pressed does not toggle it.
        for vk in _WATCHED:
            self._down[vk] = self._is_down(vk)
        self.active = True
        return True

    def stop(self) -> None:
        self.active = False

    def _is_down(self, vk: int) -> bool:
        try:
            return bool(self._get_state(vk) & 0x8000)
        except Exception:
            return False

    def poll(self) -> None:
        """Fire ``on_event(vk)`` once per key press (no auto-repeat)."""
        if not self.active:
            return
        for vk in _WATCHED:
            down = self._is_down(vk)
            if down and not self._down[vk]:
                try:
                    self._on_event(vk)
                except Exception:
                    pass
            self._down[vk] = down
