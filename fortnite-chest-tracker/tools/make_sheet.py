"""Preview sheet: every island state + the F1 ON/OFF transition frames."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "runtime", "site"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])
import chest_tracker.island as island_mod  # noqa: E402
from chest_tracker import theme  # noqa: E402
from chest_tracker.tracker import Tracker  # noqa: E402

S = 2.5


def build(state):
    t = Tracker("")
    if state == "off":
        t.enabled = False
        return t
    t.connected_event()
    t.drain()
    if state == "connected":
        for _ in range(6):
            t.chest("common")
        t.drain()
        t.session_started -= 61
    elif state == "disconnected":
        for _ in range(12):
            t.chest("common")
        t.drain()
        t.session_started -= 754
        t.disconnected_event()
        t.drain()
    elif state == "pop":
        for _ in range(7):
            t.chest("legendary")
        t.drain()
    return t


def view_for(t, width=3000.0):
    v = island_mod.IslandView(t)
    v.screen_w = width
    v.screen_h = 200.0
    return v


rows = []
# static states
for state, caption in (
    ("connected", "Connected (F1 включён) — сундук · счётчик · время · ⏻ ON"),
    ("disconnected", "Disconnected — матч закончился"),
    ("off", "F1 выключен — хаб: ⏻ OFF + Press F1"),
):
    t = build(state)
    v = view_for(t)
    v.step()
    rows.append((caption, v))

# transition frames: F1 ON (bar fills island), then F1 OFF (bar drains)
t = build("connected")
v = view_for(t)
t.enabled = False
v.kind = "off"
v.snap()
t.enabled = True
v.step()                        # starts the "in" transition
frames = []
for frac, caption in ((0.35, "F1 ON — полоса заполняет весь островок"),
                      (0.85, "F1 ON — почти весь островок")):
    v.transition = ("in", v._last - frac * island_mod.BAR_IN)
    v.width = v.target_width * island_mod._ease_out(frac)
    v.transition = ("in", v._last)
    frames.append((caption, v))

rows.extend(frames)

ROW_H = 84
PAD = 30
W = 980
H = ROW_H * len(rows) + 30
img = QImage(int(W * S), int(H * S), QImage.Format.Format_ARGB32_Premultiplied)
p = QPainter(img)
p.scale(S, S)
p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
grad = QLinearGradient(0, 0, W, H)
grad.setColorAt(0.0, QColor("#5fa86f"))
grad.setColorAt(0.5, QColor("#3a7d4c"))
grad.setColorAt(1.0, QColor("#1c4a2b"))
p.fillRect(QRectF(0, 0, W, H), grad)

label_font = QFont(theme.family())
label_font.setPixelSize(12)
label_font.setWeight(QFont.Weight.DemiBold)

y = 16
for caption, v in rows:
    p.save()
    p.setFont(label_font)
    p.setPen(QColor(255, 255, 255, 180))
    p.drawText(QRectF(PAD, y, W - PAD * 2, 16), Qt.AlignmentFlag.AlignLeft, caption)
    rx = PAD - v.island_rect().left()
    p.translate(rx, y + 34)
    v.paint(p)
    p.restore()
    y += ROW_H
p.end()
os.makedirs(os.path.join(ROOT, "preview"), exist_ok=True)
out = os.path.join(ROOT, "preview", "sheet.png")
img.save(out)
print("saved", out)
