"""Car Finder dialog showing the TCU's last GPS fix."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from ..i18n import t
from .geofence import _TileMapView


class CarFinderDialog(QDialog):
    """Modal dialog showing the car-finder result.

    Mirrors the official app's Car Finder feature: the TCU's last GPS fix
    with the truthful fix-time, course heading, ignition state, and a small
    map preview. The dashboard's location card is *not* updated by this
    flow — the device-tracker / dashboard view stays bound to the
    server-side dashboard data, which can differ slightly.
    """

    def __init__(self, location, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("car_finder.title"))
        self.setMinimumWidth(420)
        self.setMinimumHeight(440)

        layout = QVBoxLayout(self)

        title = QLabel(t("car_finder.title"))
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Map preview
        self._map = _TileMapView(self)
        self._map.setMinimumHeight(260)
        layout.addWidget(self._map, 1)

        # Details form
        form = QFormLayout()
        coord_text = f"{location.latitude:.6f}, {location.longitude:.6f}"
        osm_url = (
            f"https://www.openstreetmap.org/?mlat={location.latitude:.6f}"
            f"&mlon={location.longitude:.6f}#map=18/"
            f"{location.latitude:.6f}/{location.longitude:.6f}"
        )
        coord_label = QLabel(f'<a href="{osm_url}">{coord_text}</a>')
        coord_label.setOpenExternalLinks(True)
        coord_label.setTextFormat(Qt.TextFormat.RichText)
        coord_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        form.addRow(t("car_finder.coordinates"), coord_label)
        form.addRow(t("car_finder.fix_time"), QLabel(location.timestamp or "—"))
        form.addRow(
            t("car_finder.speed"),
            QLabel(f"{location.speed} {location.speed_unit}"),
        )
        if location.course_heading:
            form.addRow(
                t("car_finder.heading"),
                QLabel(f"{location.course_heading}°"),
            )
        ignition_key = f"dashboard.val.{location.ignition}" if location.ignition else None
        ignition_label = (
            t(ignition_key) if ignition_key and t(ignition_key) != ignition_key
            else (location.ignition or "—")
        )
        form.addRow(t("car_finder.ignition"), QLabel(ignition_label))
        layout.addLayout(form)

        note = QLabel(t("car_finder.note"))
        note.setStyleSheet("color: gray; font-size: 11px;")
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.accept)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        # Render the map after the dialog is laid out, once we have a
        # viewport size to fit the marker into.
        self._location = location

    def showEvent(self, event):
        super().showEvent(event)
        # `set_marker` rebuilds the scene, places the marker, centers the
        # viewport on the fix, then loads tiles for the new visible area.
        # Calling it after the dialog is shown ensures the viewport size
        # has been laid out so the zoom-to-fit calculation is correct.
        self._map.set_marker(
            self._location.latitude,
            self._location.longitude,
            0.5,  # ~0.5 km comfortable view radius
        )
