"""The Dynamic Island: layout, morph animation, F1 load-bar and painting."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap

from . import icons, theme

MORPH_K = 16.0
S = theme.S                    # text scale = island height / icon height
GREY = "#8e8e93"
CHEST_WHITE = "#ededf0"        # single flat chest colour (no rarity colours)
CHEST_DARK = "#26262b"
RED = "#ff4b3f"
GREEN = "#30d158"
GOLD = "#ffc457"

# F1 transition timings (seconds)
BAR_IN = 0.40                  # load bar fills the island
BAR_HOLD = 0.12                # glints at full width
BAR_OUT = 0.34                 # bar drains back, revealing the hub

# Fortnite start: the island grows out of a dot and fills with content
OPEN_S = 1.0                   # width growth, seconds
OPEN_CONTENT_AT = 0.35         # content starts fading in here
CLOSE_S = 0.55                 # shrink + fade when the game exits

_ICON_CACHE: dict = {}


def _chest_pm(color: str, glow: str | None = None, px: int = 24, ratio: float = 2.0) -> QPixmap:
    key = ("chest", int(px * ratio), color, glow)
    pm = _ICON_CACHE.get(key)
    if pm is None:
        pm = icons.chest_pixmap(px, QColor(color), QColor(glow) if glow else None, ratio)
        _ICON_CACHE[key] = pm
    return pm


def _clock_pm(color: str, px: int = 20, ratio: float = 2.0) -> QPixmap:
    key = ("clock", int(px * ratio), color)
    pm = _ICON_CACHE.get(key)
    if pm is None:
        pm = icons.clock_pixmap(px, QColor(color), ratio)
        _ICON_CACHE[key] = pm
    return pm


def _power_pm(mode: str, variant: str, px: int = 32, ratio: float = 2.0) -> QPixmap:
    key = ("power", mode, variant, int(px * ratio))
    pm = _ICON_CACHE.get(key)
    if pm is None:
        pm = icons.power_pixmap(px, mode, variant, ratio)
        _ICON_CACHE[key] = pm
    return pm


def _font(size: float, weight=theme.QFont.Weight.DemiBold, spread: float = 0.0):
    return theme.cached_font(size, weight, spread)


def _w(text: str, font) -> float:
    return QFontMetricsF(font).horizontalAdvance(text)


def _ease_out(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return 1.0 - (1.0 - t) ** 3


def _smooth(t: float) -> float:
    """Smoothstep: gentle start and gentle landing."""
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def _ease_in(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t


@dataclass
class Comp:
    kind: str
    w: float
    h: float
    data: dict


@dataclass
class Layout:
    width: float
    height: float
    comps: list


class IslandView:
    def __init__(self, tracker, parent=None) -> None:
        self.tracker = tracker
        self.parent = parent
        self.screen_w = 1280.0
        self.screen_h = 720.0
        self.kind = "hidden"          # hidden | off | main
        self.comps: list[Comp] = []
        self.width = 0.0
        self.height = float(theme.PILL_H)
        self.target_width = 0.0
        self.motion = 0.0             # 0..1 morph progress
        self._anim = False
        self._last = time.monotonic()
        self._last_repaint = 0.0
        self._snap = True
        self.needs_clock = False
        self.position = "top"
        self._snap = True
        self.opening = None           # t0 while growing out of a dot
        self.closing = None           # (t0, width0) while shrinking away
        self.content_alpha = 1.0
        self.body_alpha = 1.0

        # F1 transition: None or (kind, t0) with kind in {"in", "out"}
        self.transition = None
        self._transition_kind = None
        self._rebuild_relaxed()

    # ------------------------------------------------------------------ helpers
    def request_repaint(self) -> None:
        self._last_repaint = time.monotonic()
        if self.parent is not None:
            self.parent.update()

    def recently_painted(self, seconds: float = 0.5) -> bool:
        """True while the pop/glow effects still need frames."""
        return time.monotonic() - self._last_repaint < seconds

    def island_rect(self) -> QRectF:
        w = max(4.0, self.width)
        x = (self.screen_w - w) / 2.0
        if self.position == "middle":
            y = (self.screen_h - self.height) / 2.0
        elif self.position == "bottom":
            y = self.screen_h - self.height - theme.MARGIN_TOP
        else:
            y = theme.MARGIN_TOP
        return QRectF(x, y, w, self.height)

    def animating(self) -> bool:
        return (self.transition is not None or self.motion < 1.0
                or self.opening is not None or self.closing is not None)

    # ------------------------------------------------------------------ state
    def _clock_text(self) -> str:
        """Local time of this computer."""
        return time.strftime("%H:%M")

    def _kind(self) -> str:
        t = self.tracker
        if not t.panel_open():
            return "hidden"
        return "main" if t.enabled else "off"

    def _build(self) -> Layout:
        t = self.tracker
        pad = theme.PAD_X

        # -- tracking off: red dot + OFF + "Press F1"
        if not t.enabled:
            label_font = _font(11.5, theme.QFont.Weight.DemiBold)
            hint = "Press F1"
            hint_font = _font(8.5, theme.QFont.Weight.Medium)
            label = "OFF"
            comps = [
                Comp("power", 19, 19, {"mode": "off"}),
                Comp("text", _w(label, label_font), 11.5,
                     {"text": label, "font": label_font, "color": "#ffffff", "dy": -0.5}),
                Comp("text", _w(hint, hint_font), 8.5,
                     {"text": hint, "font": hint_font, "color": GREY, "dy": 4.5}),
            ]
            w = pad * 2 + sum(c.w for c in comps) + theme.INNER_GAP * 1.4 * (len(comps) - 1)
            return Layout(w, theme.PILL_H, comps)

        # -- tracking on: chest · total · clock · local time · green dot
        n_text = str(t.chests)
        nfont = theme.num_font(17, theme.QFont.Weight.Bold, 0.2)
        tfont = theme.num_font(11.5, theme.QFont.Weight.Medium, 0.4)
        now_text = self._clock_text()
        comps = [
            Comp("chest", 18, 18, {"color": CHEST_WHITE}),
            Comp("text", _w(n_text, nfont), 17,
                 {"text": n_text, "font": nfont, "color": "#ffffff", "flash": True}),
            Comp("gap", 2.5, 4, {}),
            Comp("clock", 14, 14, {}),
            Comp("text", _w(now_text, tfont), 11.5, {"text": now_text, "font": tfont, "color": "#b4b4bd"}),
            Comp("gap", 2.0, 4, {}),
            Comp("power", 19, 19, {"mode": "on"}),
        ]
        w = pad * 2 + sum(c.w for c in comps) + theme.INNER_GAP * (len(comps) - 1)
        return Layout(w, theme.PILL_H, comps)

    def _rebuild_relaxed(self) -> None:
        lay = self._build()
        self.kind = self._kind()
        self.comps = lay.comps
        self.target_width = lay.width
        self.height = lay.height
        if self.kind == "hidden":
            self.width = 0.0
            self.body_alpha = 0.0
            self.content_alpha = 0.0
        else:
            self.width = lay.width
            self.motion = 1.0
        self.needs_clock = self.kind == "main"

    # ------------------------------------------------------------------ animation
    def _width_hint(self) -> float:
        """Island width the load bar fills out to."""
        lay = self._build()
        if self.kind == "main":
            return max(lay.width, 122.0)
        return max(lay.width, 104.0)

    def step(self) -> None:
        now = time.monotonic()
        dt = min(0.08, now - self._last)
        self._last = now
        t = self.tracker
        want = self._build()
        kind = self._kind()

        if kind != self.kind:
            prev = self.kind
            if prev == "hidden":
                # Fortnite is up (+delay): grow out of a dot, then fill with content
                self.comps = want.comps
                self.target_width = want.width
                self.width = theme.PILL_H
                self.motion = 1.0
                self.content_alpha = 0.0
                self.body_alpha = 0.0
                self.transition = None
                self.closing = None
                self.opening = now
            elif kind == "hidden":
                # Fortnite closed: shrink back into a dot and fade out
                self.closing = (now, max(self.width, theme.PILL_H))
                self.opening = None
                self.transition = None
            elif kind == "main":
                # F1 ON: a load bar sweeps across the whole island, then the
                # tracker layout settles in.
                self.width = 0.0
                self.motion = 1.0
                self.transition = ("in", now)
                self.target_width = self._width_hint()
                self.comps = want.comps
            else:
                # F1 OFF: the bar drains and the hub slides back in.
                self.transition = ("out", now)
                self.target_width = max(self.width, self._width_hint())
                self.comps = want.comps
            self.kind = kind
            self.needs_clock = kind == "main"
            self._anim = True
        elif kind == "main":
            texts = [c.data.get("text") for c in want.comps]
            if (texts != [c.data.get("text") for c in self.comps]
                    or abs(want.width - self.target_width) > 0.4):
                if (abs(want.width - self.target_width) > 0.4
                        and self.transition is None and self.opening is None):
                    self.motion = min(self.motion, 0.5)
                self.comps = want.comps
                self.target_width = want.width
                self._anim = True

        if self.opening is not None:
            e = now - self.opening
            self.width = theme.PILL_H + (self.target_width - theme.PILL_H) * _smooth(e / OPEN_S)
            self.body_alpha = min(1.0, e / 0.25)
            self.content_alpha = _smooth((e - OPEN_CONTENT_AT) / (OPEN_S - OPEN_CONTENT_AT))
            if e >= OPEN_S:
                self.opening = None
                self.width = self.target_width
                self.body_alpha = 1.0
                self.content_alpha = 1.0
            self._anim = True
        elif self.closing is not None:
            t0, w0 = self.closing
            e = now - t0
            self.content_alpha = 1.0 - min(1.0, e / 0.2)
            self.width = theme.PILL_H + (w0 - theme.PILL_H) * (1.0 - _smooth(e / 0.4))
            self.body_alpha = 1.0 - min(1.0, max(0.0, (e - 0.35) / 0.2))
            if e >= CLOSE_S:
                self.closing = None
                self.width = 0.0
                self.body_alpha = 0.0
                self.content_alpha = 0.0
            self._anim = True
        else:
            if self.transition is not None:
                phase, t0 = self.transition
                if phase == "in":
                    elapsed = now - t0
                    if elapsed < BAR_IN:
                        self.width = self.target_width * _ease_out(elapsed / BAR_IN)
                    elif elapsed < BAR_IN + BAR_HOLD:
                        self.width = self.target_width
                    else:
                        self.width = self.target_width
                        self.motion = 0.82            # content fades in right away
                        self.transition = None
                else:
                    elapsed = now - t0
                    drained = 1.0 - _ease_in(elapsed / BAR_OUT)
                    self.width = max(want.width * 0.55, self.target_width * drained)

            if self.kind != "hidden":
                if self.transition is None or self.transition[0] != "in":
                    if self.motion < 1.0:
                        k = 1.0 - math.exp(-MORPH_K * dt)
                        self.motion = min(1.0, self.motion + k * (1.6 - self.motion))
                        self._anim = True
                    target = self.target_width if self.transition is None else self.width
                    w = self.width + (target - self.width) * (1.0 - math.exp(-MORPH_K * dt))
                    if abs(target - w) < 0.3:
                        w = target
                    if w != self.width:
                        self.width = w
                        self._anim = True
                else:
                    self._anim = True

        if self._anim:
            self._anim = False
            self.request_repaint()

    def snap(self) -> None:
        """Jump straight to the new size (used by CLI/tests, not by F1)."""
        if self.kind == "hidden" or self.opening is not None or self.closing is not None:
            return
        want = self._build()
        self.comps = want.comps
        self.target_width = want.width
        self.width = want.width
        self.motion = 1.0
        self.transition = None
        self.request_repaint()

    # ------------------------------------------------------------------ primitives
    def _power(self, p: QPainter, r: QRectF, mode: str, variant: str = "badge") -> None:
        """Status light: plain green (tracking) or red (off), no symbol."""
        base = QColor(RED if mode == "off" else GREEN)
        d = min(r.width(), r.height()) * 0.62
        c = r.center()
        p.setPen(Qt.PenStyle.NoPen)
        halo = QColor(base)
        halo.setAlpha(70)
        p.setBrush(halo)
        p.drawEllipse(c, d / 2 + 2.4, d / 2 + 2.4)
        p.setBrush(base)
        p.drawEllipse(c, d / 2, d / 2)

    def _chest(self, p: QPainter, r: QRectF, color: str, pop: bool = False) -> None:
        t = self.tracker
        scale = 1.0
        age = time.monotonic() - t.pop_at
        if pop and t.enabled and age < 0.9:
            scale = 1.0 + 0.18 * math.exp(-6.0 * age)
        glow = GOLD if (pop and t.enabled) else None
        pm = _chest_pm(color, glow, int(r.height()), 2.0)
        size = pm.width() / pm.devicePixelRatio()
        p.save()
        p.translate(r.center())
        p.scale(scale * (r.height() / 24.0), scale * (r.height() / 24.0))
        p.drawPixmap(QPointF(-size / 2, -size / 2), pm)
        p.restore()
        if pop and t.enabled and age < 0.6:
            u = age / 0.6
            ring = QColor(GOLD)
            ring.setAlpha(int(170 * (1 - u)))
            p.setPen(QPen(ring, 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            rr = r.height() / 2 + 1 + 6 * _ease_out(u)
            p.drawEllipse(r.center(), rr, rr)
            p.setPen(Qt.PenStyle.NoPen)

    def _clock(self, p: QPainter, r: QRectF) -> None:
        pm = _clock_pm(GREY, int(r.height() + 4), 2.0)
        size = pm.width() / pm.devicePixelRatio()
        p.drawPixmap(QPointF(r.center().x() - size / 2, r.center().y() - size / 2), pm)

    # ------------------------------------------------------------------ F1 bar
    def _paint_bar(self, p: QPainter, r: QRectF, rad: float, progress: float, accent: str) -> None:
        fill = QRectF(r.left(), r.top(), max(0.0, r.width() * min(1.0, progress)), r.height())
        if fill.width() < 1.0:
            return
        path = QPainterPath()
        # inset so the bar sits inside the rim; clip keeps the island silhouette
        inner = fill.adjusted(2.0, 2.0, -2.0, -2.0)
        if inner.width() <= 0 or inner.height() <= 0:
            return
        path.addRoundedRect(inner, (inner.height()) / 2, (inner.height()) / 2)
        grad = QLinearGradient(inner.topLeft(), inner.bottomLeft())
        top = QColor(accent).lighter(125)
        bottom = QColor(accent).darker(135)
        grad.setColorAt(0.0, top)
        grad.setColorAt(1.0, bottom)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawPath(path)

        # moving light streak over the filled part
        if 0.02 < progress < 1.0:
            head_x = inner.right() - inner.width() * 0.08
            shine = QColor(255, 255, 255, 150)
            pen = QPen(shine, max(1.0, inner.height() * 0.18))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawLine(QPointF(head_x, inner.top() + inner.height() * 0.3),
                       QPointF(head_x, inner.bottom() - inner.height() * 0.3))

    # ------------------------------------------------------------------ paint
    def paint(self, p: QPainter) -> None:
        if self.kind == "hidden" and self.closing is None:
            return                                   # Fortnite is not running: draw nothing
        if self.body_alpha <= 0.0 or self.width < 2.0:
            return

        r = self.island_rect()
        rad = min(r.height() / 2.0, r.width() / 2.0)
        body = QPainterPath()
        body.addRoundedRect(r, rad, rad)

        t = self.tracker
        status_on = t.enabled and self.kind == "main"
        # calm by default: the halo only brightens for ~0.9 s after a chest is counted
        chest_age = time.monotonic() - t.pop_at
        pulse = max(0.0, 1.0 - chest_age / 0.9) if status_on else 0.0
        accent = GREEN if (t.enabled or (self.transition or (None,))[0] == "in") else RED
        glow = QColor(accent)
        glow.setAlpha(int(16 + 44 * pulse) if status_on else 0)

        p.setOpacity(self.body_alpha)
        for spread, alpha in ((12.0, 20), (6.0, 22)):
            sh = QPainterPath()
            grow = spread + pulse * 2.0
            sh.addRoundedRect(r.adjusted(-grow / 2, -grow / 2, grow / 2, grow / 2), rad + grow / 2, rad + grow / 2)
            p.fillPath(sh, QColor(0, 0, 0, 140 if self.transition else alpha))
            if status_on:
                p.fillPath(sh, glow)

        p.fillPath(body, theme.ISLAND)
        p.setPen(QPen(theme.ISLAND_EDGE, 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(body)
        p.setPen(Qt.PenStyle.NoPen)

        # F1 ON: the island *is* the progress bar
        if self.transition is not None and self.transition[0] == "in" and self.target_width > 0:
            progress = r.width() / self.target_width
            self._paint_bar(p, r, rad, min(1.0, progress), GREEN)
            if progress < 0.96:
                p.setOpacity(1.0)
                return
            # bar completed: the content settles in over the full bar
            self.motion = 0.36

        if self.width < 8.0 or self.content_alpha <= 0.0:
            p.setOpacity(1.0)
            return

        # content is centred in the current body and clipped to it, so while
        # the island grows it is revealed from the middle instead of spilling out
        total = sum(c.w + (0.0 if c.kind == "gap" else theme.INNER_GAP) for c in self.comps)
        if self.comps and self.comps[-1].kind != "gap":
            total -= theme.INNER_GAP
        x = r.center().x() - total / 2.0
        cy = r.center().y()
        p.save()
        p.setClipPath(body)
        p.setOpacity(self.body_alpha * min(1.0, 0.25 + self.motion) * self.content_alpha)
        for c in self.comps:
            if c.kind == "gap":
                x += c.w
                continue
            rect = QRectF(x, cy - c.h / 2.0, c.w, c.h)
            if c.kind == "chest":
                self._chest(p, rect, c.data.get("color", CHEST_WHITE), pop=True)
            elif c.kind == "clock":
                self._clock(p, rect)
            elif c.kind == "power":
                self._power(p, rect, c.data.get("mode", "on"), c.data.get("variant", "badge"))
            elif c.kind == "text":
                font = c.data["font"]
                p.setFont(font)
                col = QColor(c.data["color"])
                if c.data.get("flash") and t.enabled:
                    age = time.monotonic() - t.pop_at
                    if age < 0.6:                      # gold -> white as the count settles
                        u = _ease_out(age / 0.6)
                        gold = QColor(GOLD)
                        col = QColor(
                            round(gold.red() + (col.red() - gold.red()) * u),
                            round(gold.green() + (col.green() - gold.green()) * u),
                            round(gold.blue() + (col.blue() - gold.blue()) * u),
                        )
                p.setPen(col)
                fm = QFontMetricsF(font)
                p.drawText(QPointF(x, cy + fm.ascent() - fm.height() / 2 + 1.0 + c.data.get("dy", 0.0)),
                           c.data["text"])
            x += c.w + theme.INNER_GAP
        p.restore()
        p.setOpacity(1.0)
