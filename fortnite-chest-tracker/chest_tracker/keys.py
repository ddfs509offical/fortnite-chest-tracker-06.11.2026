"""Hotkey bindings: which key / mouse button triggers which action.

Pure logic, no Qt. Keys are Windows virtual-key codes, so a binding can be any
keyboard key *or* a mouse button (middle = 0x04, side buttons = 0x05 / 0x06).
``0`` means "not assigned".
"""

from __future__ import annotations

ACTIONS = ("toggle", "plus", "minus", "move")

LABELS = {
    "toggle": "Включить / выключить счёт",
    "plus": "+1 сундук",
    "minus": "−1 сундук",
    "move": "Сдвинуть островок (верх / центр / низ)",
}

DEFAULTS = {
    "toggle": 0x70,   # F1
    "plus": 0x71,     # F2
    "minus": 0x72,    # F3
    "move": 0x6B,     # Numpad +
}

_NAMES = {
    0x03: "Ctrl+Break", 0x04: "Mouse middle", 0x05: "Mouse 4 (back)", 0x06: "Mouse 5 (forward)",
    0x08: "Backspace", 0x09: "Tab", 0x0D: "Enter", 0x10: "Shift", 0x11: "Ctrl", 0x12: "Alt",
    0x13: "Pause", 0x14: "Caps Lock", 0x20: "Space", 0x21: "Page Up", 0x22: "Page Down",
    0x23: "End", 0x24: "Home", 0x25: "Left", 0x26: "Up", 0x27: "Right", 0x28: "Down",
    0x2C: "Print Screen", 0x2D: "Insert", 0x2E: "Delete", 0x5B: "Left Win", 0x5C: "Right Win",
    0x5D: "Menu", 0x6A: "Numpad *", 0x6B: "Numpad +", 0x6C: "Numpad Enter", 0x6D: "Numpad -",
    0x6E: "Numpad .", 0x6F: "Numpad /", 0x90: "Num Lock", 0x91: "Scroll Lock",
    0xA0: "Left Shift", 0xA1: "Right Shift", 0xA2: "Left Ctrl", 0xA3: "Right Ctrl",
    0xA4: "Left Alt", 0xA5: "Right Alt",
    0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".", 0xBF: "/", 0xC0: "`",
    0xDB: "[", 0xDC: "\\", 0xDD: "]", 0xDE: "'",
}


def vk_name(vk: int) -> str:
    """Readable name of a virtual-key code ('' when unassigned)."""
    if not vk:
        return ""
    if vk in _NAMES:
        return _NAMES[vk]
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return chr(vk)
    if 0x60 <= vk <= 0x69:
        return f"Numpad {vk - 0x60}"
    if 0x70 <= vk <= 0x87:
        return f"F{vk - 0x6F}"
    return f"Key 0x{vk:02X}"


def _valid(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and (value == 0 or 1 <= value <= 254)


class Bindings:
    def __init__(self, stored=None) -> None:
        self.map: dict[str, int] = dict(DEFAULTS)
        if isinstance(stored, dict):
            for action in ACTIONS:
                if action in stored and _valid(stored[action]):
                    self.map[action] = stored[action]
        # a hand-edited settings.json must not bind one key to two actions
        seen: set[int] = set()
        for action in ACTIONS:
            vk = self.map[action]
            if vk and vk in seen:
                self.map[action] = 0
            seen.add(vk)

    def get(self, action: str) -> int:
        return self.map.get(action, 0)

    def name(self, action: str) -> str:
        return vk_name(self.get(action))

    def set(self, action: str, vk: int) -> list[str]:
        """Assign ``vk`` to ``action``; returns actions that lost this key."""
        freed: list[str] = []
        if vk:
            for other in ACTIONS:
                if other != action and self.map[other] == vk:
                    self.map[other] = 0
                    freed.append(other)
        self.map[action] = vk
        return freed

    def clear(self, action: str) -> None:
        self.map[action] = 0

    def reset(self) -> None:
        self.map = dict(DEFAULTS)

    def watched(self) -> set[int]:
        return {vk for vk in self.map.values() if vk}

    def actions_for(self, vk: int) -> list[str]:
        return [a for a in ACTIONS if self.map[a] == vk]

    def to_settings(self) -> dict:
        return {a: int(self.map[a]) for a in ACTIONS}
