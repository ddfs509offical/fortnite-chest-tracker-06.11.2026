"""Global key watcher: reads keyboard / mouse-button state, installs nothing.

The tracker polls ``GetAsyncKeyState`` from the Qt thread (~25 Hz). Polling only
*reads* the state: nothing sits in the input path, so the tracker can never
delay, swallow or break input for Windows, Fortnite or Easy Anti-Cheat, and the
game still receives every key as usual.

Which keys fire an event is configurable (see ``keys.Bindings``); any keyboard
key or mouse button works, including the side buttons (VK_XBUTTON1 / 2).

(The first version used a WH_KEYBOARD_LL hook. A low-level hook is called
synchronously for *every* keystroke in the whole system; if the hook thread is
late — game at full load, Python GIL busy, antivirus/EAC scanning — Windows
waits for it on each key, and the keyboard feels dead.)
"""

from __future__ import annotations

import sys

# kept for older imports / tests
VK_F1 = 0x70
VK_F2 = 0x71          # +1 chest (default)
VK_F3 = 0x72          # -1 chest (default)
VK_NUMPAD_ADD = 0x6B

VK_ESCAPE = 0x1B
_DEFAULT_WATCHED = (VK_F1, VK_F2, VK_F3, VK_NUMPAD_ADD)

# VK_LBUTTON / VK_RBUTTON are never captured: you need them to click the dialog.
_CAPTURE_FIRST, _CAPTURE_LAST = 3, 254


class KeyHook:
    """Edge-triggered key poller. Call :meth:`poll` regularly from one thread."""

    def __init__(self, on_event, watched=None) -> None:
        self._on_event = on_event
        self._watched: tuple[int, ...] = tuple(sorted(set(watched))) if watched else _DEFAULT_WATCHED
        self._down: dict[int, bool] = {vk: False for vk in self._watched}
        self._get_state = None
        self._capture = None
        self._capture_held: set[int] = set()
        self.active = False

    # ------------------------------------------------------------------ setup
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
        self.active = True
        self._resync()
        return True

    def stop(self) -> None:
        self.active = False

    def set_watched(self, vks) -> None:
        """Replace the set of keys that fire events."""
        self._watched = tuple(sorted({int(v) for v in vks if v}))
        self._resync()

    def _resync(self) -> None:
        # keys already held right now count as "down", so changing bindings
        # (or launching with a key held) never fires by itself
        self._down = {vk: (self._is_down(vk) if self.active else False) for vk in self._watched}

    def _is_down(self, vk: int) -> bool:
        try:
            return bool(self._get_state(vk) & 0x8000)
        except Exception:
            return False

    # ------------------------------------------------------------------ capture
    def start_capture(self, callback) -> None:
        """Call ``callback(vk)`` with the next pressed key / mouse button.

        ``callback(None)`` means the user pressed Esc. Normal events are paused
        while capturing.
        """
        self._capture = callback
        self._capture_held = {
            vk for vk in range(_CAPTURE_FIRST, _CAPTURE_LAST + 1) if self.active and self._is_down(vk)
        }

    def cancel_capture(self) -> None:
        self._capture = None

    @property
    def capturing(self) -> bool:
        return self._capture is not None

    def _poll_capture(self) -> None:
        for vk in range(_CAPTURE_FIRST, _CAPTURE_LAST + 1):
            if self._is_down(vk):
                if vk in self._capture_held:
                    continue                      # held since before capture: wait for release
                callback, self._capture = self._capture, None
                self._resync()
                try:
                    callback(None if vk == VK_ESCAPE else vk)
                except Exception:
                    pass
                return
            self._capture_held.discard(vk)

    # ------------------------------------------------------------------ polling
    def poll(self) -> None:
        """Fire ``on_event(vk)`` once per press (no auto-repeat)."""
        if not self.active:
            return
        if self._capture is not None:
            self._poll_capture()
            return
        for vk in self._watched:
            down = self._is_down(vk)
            if down and not self._down.get(vk, False):
                try:
                    self._on_event(vk)
                except Exception:
                    pass
            self._down[vk] = down
