"""System tray icon and menu (phase 1: window toggle, settings, quit).

Polling and notifications come in later phases; this module exposes the
signals the rest of the app needs to act on user gestures, but does no
background work itself.

If the platform reports no system tray (GNOME without AppIndicator,
headless tests, sandboxed sessions) the controller becomes a no-op:
``available`` is False and no QSystemTrayIcon is created. Callers must
check ``available`` before relying on tray-driven behaviour.
"""

import logging

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from .i18n import t
from .icons import icon as load_icon
from .platform_support import click_opens_menu, is_macos

logger = logging.getLogger(__name__)


class TrayController(QObject):
    """Owns the application's system tray icon and menu.

    Signals are emitted on user interaction; the host (``MainWindow``)
    wires them to actual behaviour. The controller deliberately does not
    touch the main window directly, so it stays testable in isolation.
    """

    show_window_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._tray: QSystemTrayIcon | None = None
        self._menu: QMenu | None = None
        self._toggle_action: QAction | None = None
        self._vehicle_name: str = ""
        self._available = QSystemTrayIcon.isSystemTrayAvailable()
        if not self._available:
            logger.info(
                "System tray not available on this platform; "
                "tray icon disabled.")
            return
        self._build_icon()
        self._build_menu()
        if self._tray is not None and self._menu is not None:
            self._tray.setContextMenu(self._menu)
            self._tray.activated.connect(self._on_activated)

    @property
    def available(self) -> bool:
        """True if a system tray was reported as available at construction time."""
        return self._available

    def show(self) -> None:
        if self._tray is not None:
            self._tray.show()

    def hide(self) -> None:
        if self._tray is not None:
            self._tray.hide()

    def set_vehicle_name(self, name: str) -> None:
        """Update the tooltip with the currently-selected vehicle name."""
        self._vehicle_name = name or ""
        self._refresh_tooltip()

    def set_status_summary(
        self,
        vehicle_name: str = "",
        battery_pct: int | None = None,
        locked: bool | None = None,
    ) -> None:
        """Update the tooltip with the latest glanceable vehicle state.

        Used by the background poller to show that data has refreshed
        even while the window is hidden. Missing fields are skipped.
        """
        if self._tray is None:
            return
        self._vehicle_name = vehicle_name or self._vehicle_name
        parts = [self._vehicle_name or t("app.name")]
        if battery_pct is not None:
            parts.append(f"{battery_pct}%")
        if locked is True:
            parts.append(t("dashboard.locked"))
        elif locked is False:
            parts.append(t("dashboard.unlocked"))
        self._tray.setToolTip(" • ".join(parts))

    def set_window_visible(self, visible: bool) -> None:
        """Update the toggle action label to mirror window visibility."""
        if self._toggle_action is None:
            return
        if visible:
            self._toggle_action.setText(t("tray.hide_window"))
        else:
            self._toggle_action.setText(t("tray.show_window"))

    def _build_icon(self) -> None:
        qi = load_icon("app-icon")
        # On macOS, NSStatusItem expects a monochrome template image so
        # the system can tint it for light / dark menu bars. Lucide SVG
        # already renders single-colour via currentColor; flagging it as
        # a mask is enough.
        if is_macos():
            qi.setIsMask(True)
        self._tray = QSystemTrayIcon(qi, self)
        self._refresh_tooltip()

    def _build_menu(self) -> None:
        self._menu = QMenu()
        self._toggle_action = QAction(t("tray.show_window"), self._menu)
        self._toggle_action.triggered.connect(self.show_window_requested.emit)
        self._menu.addAction(self._toggle_action)

        self._menu.addSeparator()

        settings_action = QAction(t("tray.settings"), self._menu)
        settings_action.triggered.connect(self.settings_requested.emit)
        self._menu.addAction(settings_action)

        quit_action = QAction(t("tray.quit"), self._menu)
        quit_action.triggered.connect(self.quit_requested.emit)
        self._menu.addAction(quit_action)

    def _refresh_tooltip(self) -> None:
        if self._tray is None:
            return
        name = self._vehicle_name or t("app.name")
        self._tray.setToolTip(name)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        # On macOS the single-click already opens the context menu via the
        # NSStatusItem convention, so we do nothing extra and let Qt handle it.
        if click_opens_menu():
            return
        if reason != QSystemTrayIcon.ActivationReason.Trigger:
            return
        self.show_window_requested.emit()
