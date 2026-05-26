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
import os

from PyQt6.QtCore import (
    QMetaType,
    QObject,
    QRectF,
    QStandardPaths,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from .i18n import t
from .icons import icon as load_icon
from .icons import pixmap as load_pixmap
from .platform_support import click_opens_menu, is_linux, is_macos

logger = logging.getLogger(__name__)

# The full app icon (rounded square + glow + car) is opaque across its
# whole bounding box, which is fine for the Linux/Windows tray slot but
# breaks macOS template images: NSStatusItem uses the alpha channel as
# a mask, so an opaque rectangle becomes a solid filled rectangle when
# tinted by the menu bar. Use the Lucide car silhouette there instead,
# which is stroke-only on a transparent background.
_TRAY_ICON_NAME_DEFAULT = "app-icon"
_TRAY_ICON_NAME_MACOS = "car"


def _tray_icon_name() -> str:
    return _TRAY_ICON_NAME_MACOS if is_macos() else _TRAY_ICON_NAME_DEFAULT


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
        low_pct: int = 0,
    ) -> None:
        """Update the tooltip and the dynamic icon with current vehicle state.

        Used by the background poller to show that data has refreshed
        even while the window is hidden. Missing fields are skipped in
        the tooltip; the icon falls back to the static app icon when no
        battery level is known. On macOS the dynamic icon is rendered as
        a monochrome template image (alpha-only) so the menu bar can
        tint it for light/dark themes. ``low_pct`` is the user's
        low-battery threshold from settings; passing 0 disables the
        low-charge glyph overlay.
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
        if battery_pct is None:
            # Restore the static icon so a previous battery glyph isn't
            # left stranded across snapshots that omit battery_level.
            qi = load_icon(_tray_icon_name())
            if is_macos():
                qi.setIsMask(True)
            self._tray.setIcon(qi)
            return
        low = low_pct > 0 and battery_pct < low_pct
        if is_macos():
            self._tray.setIcon(_battery_template_icon(battery_pct, low))
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
        # On Linux, Qt's X11 balloon pins the icon to a small fixed size and
        # ignores large pixmaps, so the app logo shows as a tiny square in a
        # lot of empty space. Talk to the freedesktop daemon directly, which
        # scales the icon to its proper notification size. Fall through to
        # the Qt balloon if no daemon answers.
        if is_linux() and _dbus_notify(
                t("app.name"), title, body,
                _notification_icon_path(), duration_ms):
            return True
        if self._tray is None:
            return False
        if not self._tray.supportsMessages():
            logger.debug("Tray does not support showMessage; skipping notification")
            return False
        # Windows/macOS: pass the full app logo as the balloon icon instead
        # of the generic system "information" glyph. Always the colored
        # app-icon (not the macOS "car" template variant): on Windows the
        # daemon renders this QIcon; on macOS the overload is ignored and
        # Notification Center shows the .app bundle icon anyway.
        balloon_icon = QIcon()
        for sz in (64, 128, 256):
            balloon_icon.addPixmap(load_pixmap(_TRAY_ICON_NAME_DEFAULT, sz))
        self._tray.showMessage(title, body, balloon_icon, duration_ms)
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
        qi = load_icon(_tray_icon_name())
        # On macOS, NSStatusItem expects a monochrome template image so
        # the system can tint it for light / dark menu bars. The Lucide
        # car silhouette is stroke-only on a transparent background, so
        # the alpha channel acts as a clean mask; flagging it is enough.
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


# -- freedesktop (Linux) notifications --------------------------------------

_NOTIFY_ICON_PATH: str | None = None


def _notification_icon_path() -> str | None:
    """Render the app logo to a cached PNG for freedesktop notifications.

    Passed as the ``image-path`` hint, which the daemon scales to its own
    notification-image size, so we render the SVG large (256px) once per
    process and reuse the file. Returns None if the cache can't be written
    (the notification still fires, just without a custom icon).
    """
    global _NOTIFY_ICON_PATH
    if _NOTIFY_ICON_PATH is not None:
        return _NOTIFY_ICON_PATH or None
    _NOTIFY_ICON_PATH = ""  # sentinel: tried; don't retry on later calls
    cache_dir = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.CacheLocation)
    if not cache_dir:
        return None
    try:
        os.makedirs(cache_dir, exist_ok=True)
        path = os.path.join(cache_dir, "notification-icon.png")
        if load_pixmap(_TRAY_ICON_NAME_DEFAULT, 256).save(path, "PNG"):
            _NOTIFY_ICON_PATH = path
            return path
    except OSError as exc:
        logger.debug("Could not cache notification icon: %s", exc)
    return None


def _dbus_notify(app_name: str, title: str, body: str,
                 icon_path: str | None, duration_ms: int) -> bool:
    """Fire a notification via org.freedesktop.Notifications (Linux only).

    Returns True if the daemon accepted the call, False if the session bus
    or the daemon isn't reachable so the caller can fall back to Qt's own
    balloon. ``replaces_id`` (uint) and ``actions`` (string array) are
    built explicitly because PyQt's type inference would otherwise marshal
    them as the wrong D-Bus types and the call would be rejected.
    """
    from PyQt6.QtDBus import QDBusArgument, QDBusConnection, QDBusMessage

    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        return False
    replaces_id = QDBusArgument()
    replaces_id.add(0, QMetaType.Type.UInt.value)
    actions = QDBusArgument()
    actions.beginArray(QMetaType.Type.QString.value)
    actions.endArray()
    # The icon goes in the hints as the notification image, NOT in the
    # app_icon parameter: daemons render app_icon as a small application
    # badge but the image hint at the full notification-image size. Set
    # both the spec 1.2 ("image-path") and 1.1 ("image_path") spellings so
    # it works regardless of which version the daemon implements.
    hints: dict = {}
    if icon_path:
        hints = {"image-path": icon_path, "image_path": icon_path}
    # Build the call as a raw QDBusMessage rather than via QDBusInterface:
    # QDBusInterface introspects the remote object on construction, and that
    # blocking round-trip, run from inside the app's event loop (where Qt is
    # already servicing the bus for the tray icon), intermittently reports
    # the interface invalid from the second call on, dropping us to the tiny
    # Qt balloon. createMethodCall does no introspection and is stable.
    msg = QDBusMessage.createMethodCall(
        "org.freedesktop.Notifications",
        "/org/freedesktop/Notifications",
        "org.freedesktop.Notifications", "Notify")
    msg.setArguments([app_name, replaces_id, "", title, body,
                      actions, hints, int(duration_ms)])
    reply = bus.call(msg)
    return (reply.type() == QDBusMessage.MessageType.ReplyMessage
            and not reply.errorName())


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


# -- macOS template variant --------------------------------------------------

def _render_battery_template(battery_pct: int, size: int, low: bool) -> QPixmap:
    """Render the battery icon as an alpha-only template image for macOS.

    NSStatusItem ignores the RGB channels of a template image and uses
    only the alpha channel as a tint mask: the menu bar then fills the
    shape with the appropriate color for the current light/dark theme.
    Everything is drawn in solid black; the bar background uses a lower
    alpha so the empty portion of the gauge reads as a softer outline.

    When ``low`` is true an exclamation glyph is overlaid in the
    top-right corner of the canvas to compensate for the loss of the
    red-bucket threshold color we use on Linux / Windows.
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

    icon_size = size - bar_height - max(1, size // 16)
    if icon_size > 0:
        base = load_pixmap(_TRAY_ICON_NAME_MACOS, icon_size)
        painter.drawPixmap((size - icon_size) // 2, 0, base)

    painter.setPen(Qt.PenStyle.NoPen)
    radius = bar_height / 2

    # Empty portion: semi-transparent so it reads as an outline.
    painter.setBrush(QColor(0, 0, 0, 90))
    painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_height),
                            radius, radius)

    # Filled portion: solid alpha.
    fill_w = int(bar_w * pct / 100)
    if fill_w > 0:
        painter.setBrush(QColor(0, 0, 0, 255))
        painter.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_height),
                                radius, radius)

    if low:
        glyph_w = max(2, size // 8)
        glyph_h = max(6, size // 3)
        gmargin = max(1, size // 16)
        gx = size - gmargin - glyph_w
        gy = gmargin
        stem_h = int(glyph_h * 0.65)
        painter.setBrush(QColor(0, 0, 0, 255))
        painter.drawRoundedRect(
            QRectF(gx, gy, glyph_w, stem_h),
            glyph_w / 2, glyph_w / 2,
        )
        dot_y = gy + stem_h + max(1, glyph_h // 8)
        painter.drawEllipse(QRectF(gx, dot_y, glyph_w, glyph_w))

    painter.end()
    return canvas


def _battery_template_icon(battery_pct: int, low: bool) -> QIcon:
    """Template-flagged QIcon variant for macOS menu bars."""
    icon = QIcon()
    for size in (16, 22, 24, 32, 48, 64):
        icon.addPixmap(_render_battery_template(battery_pct, size, low))
    icon.setIsMask(True)
    return icon
