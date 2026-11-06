"""Palette, metrics and font helpers for the Dynamic Island look."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase

# --- colours ---------------------------------------------------------------
ISLAND = QColor(8, 8, 10, 236)            # near-black island body
ISLAND_EDGE = QColor(255, 255, 255, 26)   # hairline highlight along the rim
WHITE = QColor(255, 255, 255)
DIM = QColor(255, 255, 255, 150)          # secondary text (time, labels)
FAINT = QColor(255, 255, 255, 70)         # dividers, hint text
GREEN = QColor(48, 209, 88)               # connected
RED = QColor(255, 69, 58)                 # disconnected
BLUE = QColor(10, 132, 255)
GOLD = QColor(255, 196, 87)               # chest tier accent

# --- metrics (compact island: about half the previous footprint) ------------
PILL_H = 34.0          # island height
PILL_RADIUS = 17.0
MARGIN_TOP = 10.0      # distance from the top edge of the screen
PAD_X = 11.0           # inner horizontal padding
GAP = 8.0
INNER_GAP = 5.5
MORPH_MS = 420

# text scale: island draws as if icons were 19 px tall (then scales by height/19)
S = PILL_H / 19.0

PREFERRED_FAMILIES = (
    "SF Pro Rounded",
    "SF Pro Display",
    "Segoe UI Variable Display",
    "Segoe UI",
)


def _pick_family() -> str:
    available = set(QFontDatabase.families())
    for name in PREFERRED_FAMILIES:
        if name in available:
            return name
    return "Arial"


_FAMILY: str | None = None


def family() -> str:
    global _FAMILY
    if _FAMILY is None:
        _FAMILY = _pick_family()
    return _FAMILY


def font(size: float, weight: QFont.Weight = QFont.Weight.DemiBold, spread: float = 0.0) -> QFont:
    f = QFont(family())
    f.setPixelSize(max(1, round(size)))
    f.setWeight(weight)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    if spread:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spread)
    return f


_FONT_CACHE: dict[tuple, QFont] = {}


def cached_font(size: float, weight: QFont.Weight = QFont.Weight.DemiBold, spread: float = 0.0) -> QFont:
    """Fonts are immutable in practice; cache them so repaints never allocate."""
    key = (round(size, 1), int(weight), round(spread, 2))
    f = _FONT_CACHE.get(key)
    if f is None:
        f = font(size, weight, spread)
        _FONT_CACHE[key] = f
    return f


def num_font(size: float, weight: QFont.Weight = QFont.Weight.Bold, spread: float = 0.0) -> QFont:
    """Tabular-figure font for counters, so 1 -> 12 doesn't jump."""
    f = QFont(cached_font(size, weight, spread))
    f.setFeature(QFont.Tag("tnum"), 1)
    return f
