"""Lucide SVG icon loader for the application.

Replaces 'currentColor' in SVGs with the palette text color so icons
are visible in both light and dark themes.
"""

from importlib.resources import files

from PyQt6.QtCore import QSize, QByteArray, Qt
from PyQt6.QtGui import QIcon, QPixmap, QPalette, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication


_ICONS_PKG = files("myhondaplus_desktop") / "icons"
_raw_cache: dict[str, bytes] = {}


def _text_color_hex() -> str:
    """Get the current palette text color as hex."""
    return QApplication.instance().palette().color(
        QPalette.ColorRole.WindowText).name()


def _load_svg_bytes(name: str) -> bytes:
    """Load raw SVG bytes (cached)."""
    if name not in _raw_cache:
        _raw_cache[name] = (_ICONS_PKG / f"{name}.svg").read_bytes()
    return _raw_cache[name]


def _render_pixmap(name: str, size: int) -> QPixmap:
    """Render an SVG to a transparent QPixmap with theme-aware color."""
    svg_data = _load_svg_bytes(name).replace(
        b"currentColor", _text_color_hex().encode())
    renderer = QSvgRenderer(QByteArray(svg_data))
    pm = QPixmap(QSize(size, size))
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    return pm


def icon(name: str) -> QIcon:
    """Load a Lucide SVG icon, theme-aware. Not cached (color may change)."""
    qi = QIcon()
    for sz in (16, 20, 24, 32):
        qi.addPixmap(_render_pixmap(name, sz))
    return qi


def pixmap(name: str, size: int = 16) -> QPixmap:
    """Get a sized QPixmap from a Lucide icon."""
    return _render_pixmap(name, size)
