"""Vector icons painted with QPainter (cached as QPixmaps, no image files)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)


def _pen(color: QColor, width: float) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


# ---------------------------------------------------------------- chest ----
# Drawn on a 0..22 x 0..21 grid, centred in the requested square.
def draw_chest(p: QPainter, rect: QRectF, color: QColor, *, glow: QColor | None = None, scale: float = 1.0) -> None:
    u = rect.height() / 23.0 * scale
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.translate(rect.center())
    p.translate(-11.0 * u, -10.5 * u)

    lid = QPainterPath()
    lid.moveTo(1.6 * u, 10.2 * u)
    lid.lineTo(1.6 * u, 8.4 * u)
    lid.cubicTo(1.6 * u, 3.6 * u, 3.4 * u, 3.6 * u, 8.6 * u, 3.6 * u)
    lid.lineTo(13.4 * u, 3.6 * u)
    lid.cubicTo(18.6 * u, 3.6 * u, 20.4 * u, 3.6 * u, 20.4 * u, 8.4 * u)
    lid.lineTo(20.4 * u, 10.2 * u)
    lid.closeSubpath()

    body = QPainterPath()
    body.addRoundedRect(QRectF(1.6 * u, 10.2 * u, 18.8 * u, 10.2 * u), 2.2 * u, 2.2 * u)

    if glow is not None:
        for width, alpha in ((6.0, 45), (3.4, 90)):
            c = QColor(glow)
            c.setAlpha(alpha)
            p.setPen(_pen(c, width * u))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(lid)
            p.drawPath(body)

    outline = color.darker(175)
    grad = QLinearGradient(0.0, 3.0 * u, 0.0, 21.0 * u)
    grad.setColorAt(0.0, color.lighter(142))
    grad.setColorAt(0.55, color)
    grad.setColorAt(1.0, color.darker(120))
    p.setPen(_pen(outline, 1.7 * u))
    p.setBrush(grad)
    p.drawPath(lid)
    p.drawPath(body)

    # seam between lid and body
    p.setPen(_pen(outline, 1.5 * u))
    p.drawLine(QPointF(1.9 * u, 10.3 * u), QPointF(20.1 * u, 10.3 * u))

    # metallic bands
    band = QColor(255, 255, 255, 70)
    p.setPen(_pen(band, 1.4 * u))
    p.drawLine(QPointF(7.6 * u, 3.9 * u), QPointF(7.6 * u, 10.1 * u))
    p.drawLine(QPointF(14.4 * u, 3.9 * u), QPointF(14.4 * u, 10.1 * u))

    # lock plate
    lock = QRectF(8.9 * u, 8.2 * u, 4.2 * u, 4.6 * u)
    lg = QLinearGradient(0.0, lock.top(), 0.0, lock.bottom())
    lg.setColorAt(0.0, QColor(255, 246, 214))
    lg.setColorAt(1.0, QColor(214, 180, 110))
    p.setPen(_pen(outline, 1.2 * u))
    p.setBrush(lg)
    p.drawRoundedRect(lock, 1.0 * u, 1.0 * u)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(70, 52, 22))
    p.drawEllipse(QPointF(11.0 * u, 10.3 * u), 0.62 * u, 0.62 * u)
    key = QPen(QColor(70, 52, 22), 0.8 * u)
    key.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(key)
    p.drawLine(QPointF(11.0 * u, 10.8 * u), QPointF(11.0 * u, 11.7 * u))
    p.restore()


def chest_pixmap(px: int, color: QColor, glow: QColor | None = None, ratio: float = 2.0) -> QPixmap:
    pm = QPixmap(int(px * ratio), int(px * ratio))
    pm.setDevicePixelRatio(ratio)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    draw_chest(p, QRectF(0, 0, px, px), color, glow=glow)
    p.end()
    return pm


# ---------------------------------------------------------------- clock ----
def draw_clock(p: QPainter, rect: QRectF, color: QColor) -> None:
    d = min(rect.width(), rect.height())
    c = rect.center()
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    # stopwatch crown + side buttons
    crown = QPainterPath()
    crown.addRoundedRect(QRectF(c.x() - d * 0.11, rect.top() + d * 0.03, d * 0.22, d * 0.1), d * 0.04, d * 0.04)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawPath(crown)
    stem = _pen(color, max(1.4, d * 0.085))
    p.setPen(stem)
    p.drawLine(QPointF(c.x(), rect.top() + d * 0.11), QPointF(c.x(), rect.top() + d * 0.2))
    p.drawLine(QPointF(c.x() - d * 0.2, rect.top() + d * 0.2), QPointF(c.x() - d * 0.3, rect.top() + d * 0.12))
    p.drawLine(QPointF(c.x() + d * 0.2, rect.top() + d * 0.2), QPointF(c.x() + d * 0.3, rect.top() + d * 0.12))
    # dial
    r = QRectF(0, 0, d * 0.84, d * 0.84)
    r.moveCenter(QPointF(c.x(), rect.top() + d * 0.16 + d * 0.42))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(_pen(color, max(1.3, d * 0.095)))
    p.drawEllipse(r)
    p.drawLine(r.center(), QPointF(r.center().x(), r.top() + r.height() * 0.27))
    p.drawLine(r.center(), QPointF(r.center().x() + r.width() * 0.25, r.center().y()))
    p.restore()


def clock_pixmap(px: int, color: QColor, ratio: float = 2.0) -> QPixmap:
    pm = QPixmap(int(px * ratio), int(px * ratio))
    pm.setDevicePixelRatio(ratio)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    draw_clock(p, QRectF(0, 0, px, px), color)
    p.end()
    return pm


# --------------------------------------------------------------- status ----
def draw_face(p: QPainter, rect: QRectF, color: QColor, happy: bool) -> None:
    """The little face from the sketch: dot eye + smile (or a flat line)."""
    h = rect.height()
    cx, cy = rect.center().x(), rect.center().y()
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawEllipse(QPointF(cx, cy - h * 0.19), h * 0.075, h * 0.075)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(_pen(color, max(1.3, h * 0.06)))
    path = QPainterPath()
    if happy:
        path.moveTo(cx - h * 0.19, cy - h * 0.03)
        path.quadTo(cx, cy + h * 0.27, cx + h * 0.19, cy - h * 0.03)
    else:
        path.moveTo(cx - h * 0.15, cy + h * 0.09)
        path.quadTo(cx, cy + h * 0.16, cx + h * 0.15, cy + h * 0.09)
    p.drawPath(path)
    p.restore()


def draw_status_pill(p: QPainter, rect: QRectF, color: QColor, on: bool) -> None:
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    tint = QColor(color)
    tint.setAlpha(40 if on else 30)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(tint)
    p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
    rim = QColor(color)
    rim.setAlpha(60)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(rim, 1.0))
    p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), rect.height() / 2, rect.height() / 2)
    face = QRectF(rect.left() + 3.0, rect.top(), rect.height(), rect.height())
    draw_face(p, face, color, on)
    p.restore()


# ---------------------------------------------------------------- power ----
POWER_ON_FILL = QColor("#0b0b0d")     # black disc, white glyph
POWER_OFF_FILL = QColor("#ff4b3f")    # red disc, white glyph (the reference)
POWER_IDLE = QColor("#8e8e93")        # outline only, for "no session yet"


def draw_power(p: QPainter, rect: QRectF, mode: str, variant: str = "badge") -> None:
    """⏻ mark exactly like the reference sheet:
    badge = filled disc + white glyph (red off / black on), outline = ring + dark glyph."""
    d = min(rect.width(), rect.height())
    c = rect.center()
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    if mode == "off":
        disc, glyph = POWER_OFF_FILL, QColor(255, 255, 255)
    elif mode == "on":
        disc, glyph = POWER_ON_FILL, QColor(255, 255, 255)
    else:
        disc, glyph = None, QColor("#0b0b0d")

    if variant == "outline":
        ring = QPen(QColor(255, 255, 255, 62) if glyph is not None else disc, 1.0)
        p.setPen(ring)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(c.x() - d / 2 + 0.5, c.y() - d / 2 + 0.5, d - 1, d - 1))

    r = d * (0.29 if variant == "badge" else 0.34)
    if disc is not None and variant == "badge":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(disc)
        p.drawEllipse(c, d * 0.48, d * 0.48)

    stroke = max(1.2, d * 0.075)
    ring = QPainterPath()
    box = QRectF(c.x() - r, c.y() - r + d * 0.05, 2 * r, 2 * r)
    ring.arcMoveTo(box, 90 + 50)
    ring.arcTo(box, 90 + 50, -(360 - 100))
    arc = QPen(glyph, stroke)
    arc.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(arc)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(ring)

    stem = QPen(glyph, stroke)
    stem.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(stem)
    p.drawLine(QPointF(c.x(), c.y() - r * 1.12), QPointF(c.x(), c.y() - r * 0.02))
    p.restore()


def power_pixmap(px: int, mode: str, variant: str = "badge", ratio: float = 2.0) -> QPixmap:
    pm = QPixmap(int(px * ratio), int(px * ratio))
    pm.setDevicePixelRatio(ratio)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    draw_power(p, QRectF(0, 0, px, px), mode, variant)
    p.end()
    return pm
