"""Build app.ico: a black Dynamic Island with chest + ⏻ on it."""

import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "runtime", "site"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])
from chest_tracker import icons  # noqa: E402


def render(size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    s = size / 64.0
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(10, 10, 12))
    p.drawRoundedRect(QRectF(3 * s, 10 * s, 58 * s, 44 * s), 22 * s, 22 * s)
    icons.draw_chest(p, QRectF(11 * s, 23 * s, 18 * s, 18 * s), QColor("#ededf0"))
    icons.draw_power(p, QRectF(34 * s, 21 * s, 22 * s, 22 * s), "on", "badge")
    p.end()
    return img


def ico_bytes(sizes=(16, 24, 32, 48, 64, 128, 256)) -> bytes:
    blobs = []
    for size in sizes:
        img = render(size)
        data = QByteArray()
        buf = QBuffer(data)
        buf.open(QBuffer.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        buf.close()
        blobs.append((size, bytes(data)))
    header = struct.pack("<HHH", 0, 1, len(blobs))
    offset = 6 + 16 * len(blobs)
    entries = b""
    payload = b""
    for size, blob in blobs:
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
        payload += blob
    return header + entries + payload


def main() -> int:
    ico = os.path.join(ROOT, "app.ico")
    with open(ico, "wb") as fh:
        fh.write(ico_bytes())
    os.makedirs(os.path.join(ROOT, "preview"), exist_ok=True)
    render(256).save(os.path.join(ROOT, "preview", "icon_256.png"))
    print("wrote", ico, os.path.getsize(ico), "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
