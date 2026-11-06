"""Global key watcher: F1 = on/off, Numpad + = move the island.

A WH_KEYBOARD_LL user-mode hook — the same mechanism every global-hotkey app
uses. It only *observes* keys (never blocks them, never injects, never touches
another process), so Fortnite keeps receiving F1 as usual.

Callbacks fire on the hook thread; ``on_event`` is therefore only allowed to
set a flag, and the Qt thread does the real work.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import threading

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_QUIT = 0x0012
VK_F1 = 0x70
VK_NUMPAD_ADD = 0x6B

LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wt.WPARAM, wt.LPARAM)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wt.DWORD),
        ("scanCode", wt.DWORD),
        ("flags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class KeyHook:
    def __init__(self, on_event) -> None:
        self._on_event = on_event
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._hook = None
        self._proc = None
        self.active = False

    def start(self) -> bool:
        self._thread = threading.Thread(target=self._run, name="keyhook", daemon=True)
        self._thread.start()
        self._thread.join(1.0)
        return self.active

    def stop(self) -> None:
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread is not None:
            self._thread.join(1.0)

    def _run(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()

        def low_level(n_code, w_param, l_param):  # noqa: ANN001
            try:
                if n_code == 0 and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    vk = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents.vkCode
                    if vk in (VK_F1, VK_NUMPAD_ADD):
                        self._on_event(vk)
            except Exception:
                pass
            return user32.CallNextHookEx(None, n_code, w_param, l_param)

        self._proc = HOOKPROC(low_level)
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, None, 0)
        self.active = self._hook is not None
        if not self.active:
            return
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        user32.UnhookWindowsHookEx(self._hook)
        self.active = False
