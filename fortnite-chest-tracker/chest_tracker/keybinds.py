"""Small settings window: click an action, press any key or mouse button."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from .keys import ACTIONS, LABELS

_STYLE = """
QDialog { background: #131316; }
QLabel { color: #e6e6ea; font-size: 13px; }
QLabel#hint { color: #8e8e93; font-size: 12px; }
QPushButton {
    background: #232328; color: #ffffff; border: 1px solid #34343b;
    border-radius: 8px; padding: 7px 14px; font-size: 13px;
}
QPushButton:hover { background: #2c2c33; }
QPushButton:focus { border: 1px solid #30d158; }
QPushButton[waiting="true"] { background: #1e3a28; border: 1px solid #30d158; }
QPushButton#clear { padding: 7px 10px; color: #b4b4bd; }
"""


class KeyBindDialog(QDialog):
    """Rebind actions. ``hotkey`` is the KeyHook (does the capturing),
    ``on_change`` is called after every change so the app can save it."""

    def __init__(self, bindings, hotkey, on_change, parent=None) -> None:
        super().__init__(parent)
        self.bindings = bindings
        self.hotkey = hotkey
        self.on_change = on_change
        self._pending: str | None = None
        self._buttons: dict[str, QPushButton] = {}

        self.setWindowTitle("Fortnite Chest Tracker — клавиши")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setStyleSheet(_STYLE)
        self.setMinimumWidth(460)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        hint = QLabel("Нажмите на кнопку справа, затем нужную клавишу или кнопку мыши "
                      "(в том числе боковую). Esc — отмена.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(0, 1)
        for row, action in enumerate(ACTIONS):
            grid.addWidget(QLabel(LABELS[action]), row, 0)
            bind = QPushButton()
            bind.setMinimumWidth(150)
            bind.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            bind.clicked.connect(lambda _=False, a=action: self._capture(a))
            grid.addWidget(bind, row, 1)
            clear = QPushButton("×")
            clear.setObjectName("clear")
            clear.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            clear.setToolTip("Снять привязку")
            clear.clicked.connect(lambda _=False, a=action: self._clear(a))
            grid.addWidget(clear, row, 2)
            self._buttons[action] = bind
        root.addLayout(grid)

        buttons = QHBoxLayout()
        reset = QPushButton("Сбросить на F1 / F2 / F3")
        reset.clicked.connect(self._reset)
        close = QPushButton("Готово")
        close.clicked.connect(self.accept)
        buttons.addWidget(reset)
        buttons.addStretch(1)
        buttons.addWidget(close)
        root.addLayout(buttons)

        self._refresh()

    # ------------------------------------------------------------------ view
    def _refresh(self) -> None:
        for action, button in self._buttons.items():
            waiting = action == self._pending
            button.setText("нажмите клавишу…" if waiting else (self.bindings.name(action) or "не назначено"))
            button.setProperty("waiting", waiting)
            button.style().unpolish(button)
            button.style().polish(button)

    # ------------------------------------------------------------------ actions
    def _capture(self, action: str) -> None:
        self._pending = action
        self.hotkey.start_capture(self._captured)
        self._refresh()

    def _captured(self, vk) -> None:
        action, self._pending = self._pending, None
        if action is not None and vk is not None:
            self.bindings.set(action, vk)
            self.on_change()
        self._refresh()

    def _clear(self, action: str) -> None:
        self._cancel()
        self.bindings.clear(action)
        self.on_change()
        self._refresh()

    def _reset(self) -> None:
        self._cancel()
        self.bindings.reset()
        self.on_change()
        self._refresh()

    def _cancel(self) -> None:
        self.hotkey.cancel_capture()
        self._pending = None

    def done(self, result) -> None:      # accept / reject / window close
        self._cancel()
        self._refresh()
        super().done(result)
