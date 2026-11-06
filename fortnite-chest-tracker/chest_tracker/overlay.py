"""Overlay window: transparent, click-through, always on top, renders the island."""

from __future__ import annotations

import sys

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QLinearGradient, QPainter
from PySide6.QtWidgets import QWidget

from .island import IslandView

if sys.platform == "win32":
    import ctypes

    _u32 = ctypes.windll.user32
    GWL_EXSTYLE = -20
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_LAYERED = 0x00080000
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_NOACTIVATE = 0x08000000


class OverlayWindow(QWidget):
    """Top-most, non-activating, mouse-transparent window covering one screen."""

    PREVIEW = False

    def __init__(self, tracker) -> None:
        super().__init__(None)
        self.tracker = tracker
        self.island = IslandView(tracker, self)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setWindowTitle("Fortnite Chest Tracker")
        # the overlay must never keep the app alive
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)

        self._apply_screen()
        self._clock_interval = 1000

        self._clock = QTimer(self)
        self._clock.setInterval(1000)
        self._clock.setTimerType(Qt.TimerType.CoarseTimer)
        self._clock.timeout.connect(self._tick_clock)
        self._clock.start()

        # fast timer only ticks while something actually moves (morph, bar, pop);
        # otherwise a 1 Hz clock is enough and the overlay costs ~nothing.
        self._anim = QTimer(self)
        self._anim.setInterval(25)
        self._anim.setTimerType(Qt.TimerType.CoarseTimer)
        self._anim.timeout.connect(self._tick_anim)
        self._anim.start()

        self._watch = QTimer(self)
        self._watch.setInterval(2000)
        self._watch.timeout.connect(self._check_screen)
        self._watch.start()

    def _tick_anim(self) -> None:
        self.island.step()
        moving = self.island.animating() or self.island.recently_painted(0.6)
        self._clock_interval = 33 if moving else 1000
        if self._clock.interval() != self._clock_interval:
            self._clock.setInterval(self._clock_interval)

    POSITIONS = ("top", "middle", "bottom")

    # ------------------------------------------------------------------ screens
    def _apply_screen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        geo = screen.geometry() if screen else QRectF(0, 0, 1280, 720)
        self.setGeometry(geo)
        self.island.screen_w = float(geo.width())
        self.island.screen_h = float(geo.height())
        self._apply_position()

    def _apply_position(self) -> None:
        pos = self.tracker.settings.get("position", "top")
        self.tracker.settings["position"] = pos if pos in self.POSITIONS else "top"
        self.island.position = self.tracker.settings["position"]
        self.update()

    def cycle_position(self) -> str:
        """Numpad +: top -> middle -> bottom -> top (persisted)."""
        current = self.tracker.settings.get("position", "top")
        nxt = self.POSITIONS[(self.POSITIONS.index(current) + 1) % len(self.POSITIONS)]
        self.tracker.settings["position"] = nxt
        self.tracker.settings_store.save(self.tracker.settings)
        self._apply_position()
        return nxt

    def _check_screen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.geometry()
        if self.geometry() != geo:
            self._apply_screen()
            self.update()

    # ------------------------------------------------------------------ native
    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._native_style()

    def _native_style(self) -> None:
        if sys.platform != "win32":
            return
        hwnd = int(self.winId())
        ex = _u32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ex |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        _u32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)

    def set_visible(self, visible: bool) -> None:
        self.setVisible(visible)

    # ------------------------------------------------------------------ paint
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self.PREVIEW:
            grad = QLinearGradient(0, 0, 0, self.height())
            grad.setColorAt(0.0, QColor("#4c9a5f"))
            grad.setColorAt(0.35, QColor("#2f7a44"))
            grad.setColorAt(1.0, QColor("#173d24"))
            painter.fillRect(self.rect(), grad)
            # a hint of a sky/frame so the island reads in the screenshot
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, 14))
            painter.drawRect(QRectF(0, self.height() * 0.62, self.width(), 3))
        self.island.paint(painter)

    # ------------------------------------------------------------------ ticking
    def _tick_clock(self) -> None:
        if self.island.needs_clock:
            self.update(self.island.island_rect().adjusted(-16, -16, 16, 16).toAlignedRect())

    def refresh(self) -> None:
        self.island.step()
        self.update()


class PreviewWindow(OverlayWindow):
    PREVIEW = True
