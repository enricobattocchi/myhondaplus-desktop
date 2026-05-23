"""Platform and desktop-environment helpers used by the tray icon.

Detection is intentionally limited to what changes user-visible behaviour:
- macOS gets a different click convention (single-click opens the menu)
  and needs the tray icon flagged as "template" so the menu bar tints it.
- GNOME ships without a native system tray since 3.26; users need the
  AppIndicator / KStatusNotifierItem Support extension. This is the only
  case where Qt may report ``isSystemTrayAvailable() == True`` but the
  icon is invisible in the shell, so we surface a hint.

Everything else (KDE, XFCE, MATE, Cinnamon, LXQt, Budgie, Windows) just
works through ``QSystemTrayIcon`` without intervention.
"""

import logging
import os
import sys

logger = logging.getLogger(__name__)


def is_macos() -> bool:
    return sys.platform == "darwin"


def is_windows() -> bool:
    return sys.platform == "win32"


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def desktop_env() -> str:
    """Return the lower-cased ``XDG_CURRENT_DESKTOP`` value, or "" off Linux."""
    if not is_linux():
        return ""
    return os.environ.get("XDG_CURRENT_DESKTOP", "").lower()


def session_type() -> str:
    """Return the lower-cased ``XDG_SESSION_TYPE`` (x11 / wayland / ""), Linux only."""
    if not is_linux():
        return ""
    return os.environ.get("XDG_SESSION_TYPE", "").lower()


def is_gnome() -> bool:
    """True if the current Linux desktop session reports GNOME."""
    return "gnome" in desktop_env()


def click_opens_menu() -> bool:
    """macOS convention: single click opens the menu instead of toggling the window."""
    return is_macos()
