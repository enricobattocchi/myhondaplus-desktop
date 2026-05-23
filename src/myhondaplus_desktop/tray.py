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

from PyQt6.QtCore import QObject, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from .i18n import t
from .icons import icon as load_icon
from .icons import pixmap as load_pixmap
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
    vehicle_selected = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._tray: QSystemTrayIcon | None = None
        self._menu: QMenu | None = None
        self._toggle_action: QAction | None = None
        self._vehicle_submenu: QMenu | None = None
        self._vehicle_action_group: QActionGroup | None = None
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
        """Update the tooltip and the dynamic icon with current vehicle state.

        Used by the background poller to show that data has refreshed
        even while the window is hidden. Missing fields are skipped in
        the tooltip; the icon falls back to the static app icon when no
        battery level is known (or on macOS, where the tray icon must
        stay monochrome for the menu bar template).
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
        if is_macos():
            # macOS keeps the static template icon either way.
            return
        if battery_pct is None:
            # Restore the static icon so a previous battery bar isn't left
            # stranded across snapshots that omit battery_level.
            self._tray.setIcon(load_icon("app-icon"))
        else:
            self._tray.setIcon(_battery_bar_icon(battery_pct))

    def set_vehicles(self, vehicles: list[dict], current_vin: str) -> None:
        """Rebuild the "Vehicle" submenu when the account has more than one car.

        For single-vehicle accounts the submenu is hidden entirely so the
        menu stays uncluttered. Selection emits ``vehicle_selected`` with
        the chosen VIN; the host is expected to wire that to the same VIN
        change path the in-window combobox uses.
        """
        if self._menu is None or self._vehicle_submenu is None:
            return
        # Clear existing items
        self._vehicle_submenu.clear()
        if self._vehicle_action_group is not None:
            self._vehicle_action_group.deleteLater()
        self._vehicle_action_group = QActionGroup(self._vehicle_submenu)
        self._vehicle_action_group.setExclusive(True)

        if len(vehicles) <= 1:
            # Hide the submenu's parent action entirely.
            self._vehicle_submenu_action.setVisible(False)
            return

        self._vehicle_submenu_action.setVisible(True)
        for v in vehicles:
            vin = v.get("vin", "")
            label = v.get("name") or vin
            action = QAction(label, self._vehicle_submenu)
            action.setCheckable(True)
            action.setChecked(vin == current_vin)
            action.setData(vin)
            action.triggered.connect(
                lambda _checked, target=vin: self.vehicle_selected.emit(target))
            self._vehicle_action_group.addAction(action)
            self._vehicle_submenu.addAction(action)

    def show_notification(self, title: str, body: str,
                          duration_ms: int = 30000) -> bool:
        """Fire a desktop notification via the tray.

        Returns True on success, False if the platform doesn't support
        balloon messages (some Linux DEs, macOS without bundle, etc.) or
        if the tray itself isn't available.
        """
        if self._tray is None:
            return False
        if not self._tray.supportsMessages():
            logger.debug("Tray does not support showMessage; skipping notification")
            return False
        self._tray.showMessage(
            title, body, QSystemTrayIcon.MessageIcon.Information, duration_ms)
        return True

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

        # Vehicle submenu (hidden until the account has more than one car).
        self._vehicle_submenu = QMenu(t("tray.vehicle_submenu"), self._menu)
        self._vehicle_submenu_action = self._menu.addMenu(self._vehicle_submenu)
        self._vehicle_submenu_action.setVisible(False)

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


# -- dynamic battery-bar icon ------------------------------------------------

def _battery_color(battery_pct: int) -> QColor:
    """Traffic-light bucketing of the battery level."""
    if battery_pct >= 50:
        return QColor(34, 197, 94)   # green
    if battery_pct >= 20:
        return QColor(234, 179, 8)   # yellow
    return QColor(239, 68, 68)       # red


def _render_battery_bar(battery_pct: int, size: int) -> QPixmap:
    """Render the app icon with a horizontal battery bar along the bottom.

    Bar sits flush with the bottom edge so it never gets clipped by the
    tray slot (rings do, on tight panels). Faint grey background bar
    under the colored fill so the "empty" part is visible too.
    """
    pct = max(0, min(100, int(battery_pct)))
    canvas = QPixmap(size, size)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    bar_height = max(3, size // 7)
    side_margin = max(1, size // 16)
    bar_y = size - bar_height
    bar_x = side_margin
    bar_w = size - 2 * side_margin

    # Base icon: shrink to leave room for the bar at the bottom, center it.
    icon_size = size - bar_height - max(1, size // 16)
    if icon_size > 0:
        base = load_pixmap("app-icon", icon_size)
        painter.drawPixmap((size - icon_size) // 2, 0, base)

    painter.setPen(Qt.PenStyle.NoPen)
    radius = bar_height / 2

    # Background (empty) bar.
    painter.setBrush(QColor(120, 120, 120, 100))
    painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_height),
                            radius, radius)

    # Foreground (filled) bar.
    fill_w = int(bar_w * pct / 100)
    if fill_w > 0:
        painter.setBrush(_battery_color(pct))
        painter.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_height),
                                radius, radius)

    painter.end()
    return canvas


def _battery_bar_icon(battery_pct: int) -> QIcon:
    """QIcon with several pixmap sizes for HiDPI-friendly tray rendering."""
    icon = QIcon()
    for size in (16, 22, 24, 32, 48, 64):
        icon.addPixmap(_render_battery_bar(battery_pct, size))
    return icon
