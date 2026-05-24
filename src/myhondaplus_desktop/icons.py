"""Lucide SVG icon loader for the application.

Replaces 'currentColor' in SVGs with the palette text color so icons
are visible in both light and dark themes.
"""

from importlib.resources import files

from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication

_ICONS_PKG = files("myhondaplus_desktop") / "icons"
_raw_cache: dict[str, bytes] = {}


def _text_color_hex() -> str:
    """Get the current palette text color as hex."""
    return QApplication.instance().palette().color(
        QPalette.ColorRole.WindowText).name()


def link_color_hex() -> str:
    """Get the current palette Link color as hex.

    Qt's QLabel rich-text ignores QPalette.Link for raw ``<a>`` tags and
    falls back to a hard-coded blue (≈ #0000FF) that's unreadable on dark
    backgrounds. Inject this value via inline ``style="color: …"`` to make
    links theme-aware.
    """
    return QApplication.instance().palette().color(
        QPalette.ColorRole.Link).name()


# WCAG AA for normal text is 4.5:1. Enforce a margin above it so a sampling
# tool reads a clear pass and small surface differences stay safe.
_MIN_CONTRAST = 4.8

# Status text has no system palette role, so start from a vivid hue and
# lighten/darken it (per theme) until it clears _MIN_CONTRAST.
_POSITIVE_BASE = (22, 163, 74)   # green
_NEGATIVE_BASE = (220, 38, 38)   # red
_WARNING_BASE = (217, 119, 6)    # amber

_RGB = tuple[int, int, int]


def _relative_luminance(c: _RGB) -> float:
    def _chan(v: int) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = c
    return 0.2126 * _chan(r) + 0.7152 * _chan(g) + 0.0722 * _chan(b)


def _contrast(fg: _RGB, bg: _RGB) -> float:
    hi = max(_relative_luminance(fg), _relative_luminance(bg))
    lo = min(_relative_luminance(fg), _relative_luminance(bg))
    return (hi + 0.05) / (lo + 0.05)


def _rgb(color: QColor) -> _RGB:
    return color.red(), color.green(), color.blue()


def _blend(a: _RGB, b: _RGB, t: float) -> _RGB:
    return tuple(round(x * (1 - t) + y * t) for x, y in zip(a, b, strict=True))


def _is_dark_theme() -> bool:
    pal = QApplication.instance().palette()
    return _relative_luminance(_rgb(pal.color(QPalette.ColorRole.WindowText))) \
        > _relative_luminance(_rgb(pal.color(QPalette.ColorRole.Window)))


_pane_cache: dict[str, _RGB] = {}


def _probe_content_background(pal: QPalette) -> _RGB:
    """Render a throwaway tab page and sample the colour it is painted in.

    Styles like Fusion paint the tab pane / content panels a few shades
    lighter than ``QPalette.Window`` (e.g. #2d2d2d -> ~#454545), by an amount
    that varies with the platform, so it can't be read from the palette. This
    is the surface our labels actually sit on, so measure it directly. Done
    off-screen via ``grab()`` (no window is shown) and cached per palette.
    """
    from PyQt6.QtWidgets import QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget
    try:
        win = QMainWindow()
        tabs = QTabWidget()
        win.setCentralWidget(tabs)
        page = QWidget()
        QVBoxLayout(page).addWidget(QLabel())
        tabs.addTab(page, "")
        win.resize(200, 160)
        c = win.grab().toImage().pixelColor(100, 120)
        win.deleteLater()
        return (c.red(), c.green(), c.blue())
    except Exception:
        return _rgb(pal.color(QPalette.ColorRole.Window))


def _content_background() -> _RGB:
    pal = QApplication.instance().palette()
    key = pal.color(QPalette.ColorRole.Window).name()
    if key not in _pane_cache:
        _pane_cache[key] = _probe_content_background(pal)
    return _pane_cache[key]


def _worst_background() -> _RGB:
    """The surface text contrasts against worst: the lightest one on a dark
    theme, the darkest on a light theme. Clearing it clears the rest. Includes
    the measured content-pane colour, which the palette does not expose."""
    pal = QApplication.instance().palette()
    bgs = [_rgb(pal.color(r)) for r in (
        QPalette.ColorRole.Window, QPalette.ColorRole.Base,
        QPalette.ColorRole.Button, QPalette.ColorRole.AlternateBase)]
    bgs.append(_content_background())
    return (max if _is_dark_theme() else min)(bgs, key=_relative_luminance)


def _search_blend(start: _RGB, toward: _RGB, bg: _RGB, want_max_t: bool) -> _RGB:
    """Binary-search the blend of ``start`` toward ``toward`` that sits right
    at _MIN_CONTRAST against ``bg``. ``want_max_t`` keeps the largest blend
    still meeting the floor (dimming); otherwise the smallest that reaches it."""
    lo, hi = 0.0, 1.0
    for _ in range(24):
        t = (lo + hi) / 2
        ok = _contrast(_blend(start, toward, t), bg) >= _MIN_CONTRAST
        if ok == want_max_t:
            lo = t
        else:
            hi = t
    return _blend(start, toward, lo if want_max_t else hi)


def secondary_text_color() -> str:
    """Dimmed label colour, derived entirely from the system palette.

    Takes the theme's own text colour and dims it toward the background only
    as far as the background allows while staying at or above _MIN_CONTRAST,
    measured against the hardest palette surface. No hard-coded colours, so it
    tracks the active theme (system or forced) and never drops below AA.
    """
    pal = QApplication.instance().palette()
    fg = _rgb(pal.color(QPalette.ColorRole.WindowText))
    bg = _worst_background()
    if _contrast(fg, bg) < _MIN_CONTRAST:
        return QColor(*fg).name()  # too little headroom to dim at all
    return QColor(*_search_blend(fg, bg, bg, want_max_t=True)).name()


def _status_color(base: _RGB) -> str:
    bg = _worst_background()
    if _contrast(base, bg) >= _MIN_CONTRAST:
        return QColor(*base).name()
    toward = (255, 255, 255) if _is_dark_theme() else (0, 0, 0)
    return QColor(*_search_blend(base, toward, bg, want_max_t=False)).name()


def positive_color_hex() -> str:
    """Accessible green for positive status (charging, locked)."""
    return _status_color(_POSITIVE_BASE)


def warning_color_hex() -> str:
    """Accessible amber for pending/warning status."""
    return _status_color(_WARNING_BASE)


def negative_color_hex() -> str:
    """Accessible red for negative status (unlocked, errors)."""
    return _status_color(_NEGATIVE_BASE)


def _load_svg_bytes(name: str) -> bytes:
    """Load raw SVG bytes (cached)."""
    if name not in _raw_cache:
        _raw_cache[name] = (_ICONS_PKG / f"{name}.svg").read_bytes()
    return _raw_cache[name]


def _render_pixmap(name: str, size: int, color: str | None = None) -> QPixmap:
    """Render an SVG to a transparent QPixmap.

    Colours ``currentColor`` with ``color`` if given, otherwise the
    theme's text colour.
    """
    color_hex = color or _text_color_hex()
    svg_data = _load_svg_bytes(name).replace(
        b"currentColor", color_hex.encode())
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


def pixmap(name: str, size: int = 16, color: str | None = None) -> QPixmap:
    """Get a sized QPixmap from a Lucide icon, optionally tinted ``color``."""
    return _render_pixmap(name, size, color)
