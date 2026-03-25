"""Tests for the icon loader."""

import sys
from unittest.mock import MagicMock

# Mock Qt modules for headless testing
for mod in ["PyQt6.QtWidgets", "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtSvg"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()


def test_icon_files_exist():
    """Verify all expected icon SVG files are bundled."""
    from importlib.resources import files
    icons_dir = files("myhondaplus_desktop") / "icons"
    expected = [
        "battery-charging", "shield", "map-pin", "snowflake", "car",
        "triangle-alert", "lock", "lock-open", "settings", "zap",
        "megaphone", "calendar-clock", "refresh-cw", "log-out", "info",
        "app-icon",
    ]
    for name in expected:
        path = icons_dir / f"{name}.svg"
        assert path.is_file(), f"Missing icon: {name}.svg"


def test_translation_files_exist():
    """Verify translation JSON files are bundled."""
    from importlib.resources import files
    trans_dir = files("myhondaplus_desktop") / "translations"
    for lang in ["en", "it"]:
        path = trans_dir / f"{lang}.json"
        assert path.is_file(), f"Missing translation: {lang}.json"
