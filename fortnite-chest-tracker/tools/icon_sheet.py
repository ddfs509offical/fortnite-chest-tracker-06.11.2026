import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "runtime", "site"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])
from chest_tracker import icons  # noqa: E402

S = 2
img = QImage(330 * S, 120 * S, QImage.Format.Format_ARGB32_Premultiplied)
img.fill(Qt.GlobalColor.white)
p = QPainter(img)
p.scale(S, S)
p.save()
p.setOpacity(1.0); p.setBrush(Qt.GlobalColor.transparent); p.setPen(Qt.PenStyle.NoPen); p.drawRect(QRectF(0, 0, 330, 120))
p.restore()
x = 12
for mode, variant in (("off", "badge"), ("on", "badge"), ("idle", "outline")):
    icons.draw_power(p, QRectF(x, 24, 70, 70), mode, variant)
    x += 84
p.end()
out = os.path.join(ROOT, "preview", "power.png")
os.makedirs(os.path.dirname(out), exist_ok=True)
img.save(out)
print("saved", out)
