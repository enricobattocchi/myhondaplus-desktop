"""Tests for palette-derived accessible colours in icons.py.

Colours are not hard-coded: field labels dim the system text colour only as
far as the system background allows, and status colours start from a vivid
hue and are lightened/darkened until they clear WCAG AA. These tests assert
the contrast floor holds across light, dark, and a mid-grey theme like the
one a system dark theme (e.g. MATE, panels ~#444) produces.
"""

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

from myhondaplus_desktop.icons import (
    cool_color_hex,
    negative_color_hex,
    pixmap,
    positive_color_hex,
    secondary_text_color,
    warning_color_hex,
)

APP = QApplication.instance() or QApplication([])


def _contrast(fg_hex: str, bg: tuple[int, int, int]) -> float:
    def chan(c: int) -> float:
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    def lum(rgb):
        r, g, b = rgb
        return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)

    fg = tuple(int(fg_hex.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    hi, lo = max(lum(fg), lum(bg)), min(lum(fg), lum(bg))
    return (hi + 0.05) / (lo + 0.05)


def _surfaces(backgrounds):
    return list(backgrounds) * 4 if len(backgrounds) == 1 else list(backgrounds)


def _set_palette(text, backgrounds):
    win, base, button, alt = _surfaces(backgrounds)
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.WindowText, QColor(*text))
    pal.setColor(QPalette.ColorRole.Window, QColor(*win))
    pal.setColor(QPalette.ColorRole.Base, QColor(*base))
    pal.setColor(QPalette.ColorRole.Button, QColor(*button))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(*alt))
    APP.setPalette(pal)


# text, [surface backgrounds]
DARK = ((220, 220, 220), [(45, 45, 45), (30, 30, 30), (55, 55, 55), (50, 50, 50)])
LIGHT = ((0, 0, 0), [(240, 240, 240), (255, 255, 255), (240, 240, 240), (245, 245, 245)])
SYSTEM_GREY = ((222, 222, 222), [(68, 68, 68)])  # MATE-like dark theme, #444 panels

THEMES = {"dark": DARK, "light": LIGHT, "system_grey_444": SYSTEM_GREY}

_GETTERS = (
    secondary_text_color,
    positive_color_hex,
    negative_color_hex,
    warning_color_hex,
    cool_color_hex,
)


def test_every_colour_clears_aa_on_every_surface():
    for name, (text, backgrounds) in THEMES.items():
        _set_palette(text, backgrounds)
        surfaces = _surfaces(backgrounds)
        for getter in _GETTERS:
            hexv = getter()
            worst = min(_contrast(hexv, bg) for bg in surfaces)
            assert worst >= 4.5, f"{name}: {getter.__name__}={hexv} -> {worst:.2f}"


def test_colours_clear_aa_against_measured_content_background():
    # The real failure: text sits on the style's painted pane (lighter than
    # any palette role), so verify against the measured pane, not the palette.
    from myhondaplus_desktop.icons import _content_background
    for name, (text, backgrounds) in THEMES.items():
        _set_palette(text, backgrounds)
        pane = _content_background()
        pane_hex = "#{:02x}{:02x}{:02x}".format(*pane)
        for getter in _GETTERS:
            assert _contrast(getter(), pane) >= 4.5, (
                f"{name}: {getter.__name__}={getter()} on pane {pane_hex} "
                f"-> {_contrast(getter(), pane):.2f}")


def test_secondary_stays_dimmer_than_full_text():
    # The label must keep a visible hierarchy below full-strength values.
    for text, backgrounds in (DARK, LIGHT):
        _set_palette(text, backgrounds)
        window = _surfaces(backgrounds)[0]
        full = "#{:02x}{:02x}{:02x}".format(*text)
        assert _contrast(secondary_text_color(), window) < _contrast(full, window)


def test_colours_track_the_palette_not_a_constant():
    # Same role, different theme -> different colour. Guards against regressing
    # to hard-coded values.
    _set_palette(*DARK)
    dark_secondary = secondary_text_color()
    _set_palette(*LIGHT)
    assert secondary_text_color() != dark_secondary


def test_pixmap_accepts_color_override():
    # The charging glyph renders the lightning icon tinted green.
    pm = pixmap("zap", 16, "#4ade80")
    assert not pm.isNull()
