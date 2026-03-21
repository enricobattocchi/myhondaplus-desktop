"""Dashboard widget showing vehicle status."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QProgressBar, QFrame,
)
from PyQt6.QtCore import Qt


def _dms_to_decimal(dms: str) -> float | None:
    """Convert 'DD,MM,SS.sss' to decimal degrees."""
    try:
        parts = str(dms).split(",")
        if len(parts) == 3:
            d, m, s = float(parts[0]), float(parts[1]), float(parts[2])
            return d + m / 60 + s / 3600
        return float(dms)
    except (ValueError, TypeError):
        return None


def _card(title: str) -> tuple[QGroupBox, QVBoxLayout]:
    box = QGroupBox(title)
    box.setStyleSheet("QGroupBox { font-weight: bold; }")
    layout = QVBoxLayout(box)
    return box, layout


def _selectable(label: QLabel) -> QLabel:
    """Make a QLabel's text selectable by mouse."""
    label.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setCursor(Qt.CursorShape.IBeamCursor)
    return label


def _row(label: str, value: str = "") -> tuple[QHBoxLayout, QLabel]:
    h = QHBoxLayout()
    lbl = QLabel(label)
    lbl.setStyleSheet("color: gray;")
    val = _selectable(QLabel(value))
    h.addWidget(lbl)
    h.addStretch()
    h.addWidget(val)
    return h, val


class DashboardWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._labels = {}

        grid = QGridLayout(self)

        # Battery card
        bat_box, bat_layout = _card("\U0001F50B Battery")
        self._battery_bar = QProgressBar()
        self._battery_bar.setRange(0, 100)
        self._battery_bar.setTextVisible(True)
        bat_layout.addWidget(self._battery_bar)
        for key in ("range_km", "total_range_km", "charge_status",
                     "plug_status", "charge_mode", "time_to_charge",
                     "charge_limit_home", "charge_limit_away"):
            h, val = _row(self._nice_label(key))
            bat_layout.addLayout(h)
            self._labels[key] = val
        grid.addWidget(bat_box, 0, 0)

        # Security card
        sec_box, sec_layout = _card("\U0001F6E1 Security")
        for key in ("doors_locked", "all_doors_closed", "all_windows_closed",
                     "hood_open", "trunk_open", "lights_on",
                     "headlights", "parking_lights"):
            h, val = _row(self._nice_label(key))
            sec_layout.addLayout(h)
            self._labels[key] = val
        grid.addWidget(sec_box, 0, 1)

        # Location card
        loc_box, loc_layout = _card("\U0001F4CD Location")
        self._location_link = QLabel("")
        self._location_link.setOpenExternalLinks(True)
        self._location_link.setTextFormat(Qt.TextFormat.RichText)
        self._location_link.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction)
        loc_layout.addWidget(self._location_link)
        for key in ("home_away", "speed_kmh"):
            h, val = _row(self._nice_label(key))
            loc_layout.addLayout(h)
            self._labels[key] = val
        grid.addWidget(loc_box, 1, 0)

        # Climate card
        clim_box, clim_layout = _card("\u2744 Climate")
        for key in ("climate_active", "cabin_temp_c", "interior_temp_c"):
            h, val = _row(self._nice_label(key))
            clim_layout.addLayout(h)
            self._labels[key] = val
        grid.addWidget(clim_box, 1, 1)

        # Vehicle card
        veh_box, veh_layout = _card("\U0001F697 Vehicle")
        h, val = _row("\U0001F4CB VIN")
        veh_layout.addLayout(h)
        self._vin_label = val
        for key in ("odometer_km", "ignition"):
            h, val = _row(self._nice_label(key))
            veh_layout.addLayout(h)
            self._labels[key] = val
        grid.addWidget(veh_box, 2, 0)

        # Warnings card
        warn_box, warn_layout = _card("\u26A0 Warnings")
        self._warnings_label = _selectable(QLabel("(none)"))
        warn_layout.addWidget(self._warnings_label)
        grid.addWidget(warn_box, 2, 1)

        # Timestamp
        self._timestamp = _selectable(QLabel(""))
        self._timestamp.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._timestamp.setStyleSheet("color: gray; font-size: 11px;")
        grid.addWidget(self._timestamp, 3, 0, 1, 2)

    def set_vin(self, vin: str):
        self._vin_label.setText(vin)

    def update_status(self, status: dict):
        self._battery_bar.setValue(status.get("battery_level", 0))

        lat_raw = status.get("latitude", "")
        lon_raw = status.get("longitude", "")
        lat = _dms_to_decimal(lat_raw)
        lon = _dms_to_decimal(lon_raw)
        if lat is not None and lon is not None:
            osm_url = (f"https://www.openstreetmap.org/"
                       f"?mlat={lat:.6f}&mlon={lon:.6f}#map=17/{lat:.6f}/{lon:.6f}")
            self._location_link.setText(
                f'<a href="{osm_url}">{lat:.6f}, {lon:.6f}</a>')
        else:
            self._location_link.setText("Unknown")

        formatters = {
            "range_km": lambda v: f"{v} km",
            "total_range_km": lambda v: f"{v} km",
            "time_to_charge": lambda v: f"{v} min" if v else "—",
            "charge_limit_home": lambda v: f"{v}%",
            "charge_limit_away": lambda v: f"{v}%",
            "doors_locked": lambda v: "Locked" if v else "UNLOCKED",
            "all_doors_closed": lambda v: "Yes" if v else "NO",
            "all_windows_closed": lambda v: "Yes" if v else "NO",
            "hood_open": lambda v: "Open" if v else "Closed",
            "trunk_open": lambda v: "Open" if v else "Closed",
            "lights_on": lambda v: "On" if v else "Off",
            "climate_active": lambda v: "ON" if v else "Off",
            "cabin_temp_c": lambda v: f"{v}°C",
            "interior_temp_c": lambda v: f"{v}°C",
            "odometer_km": lambda v: f"{v:,} km",
            "speed_kmh": lambda v: f"{v} km/h",
        }

        for key, label in self._labels.items():
            value = status.get(key, "")
            fmt = formatters.get(key)
            label.setText(fmt(value) if fmt else str(value))

        # Color doors_locked
        if "doors_locked" in self._labels:
            locked = status.get("doors_locked", False)
            self._labels["doors_locked"].setStyleSheet(
                "color: green; font-weight: bold;" if locked
                else "color: red; font-weight: bold;")

        warnings = status.get("warning_lamps", [])
        self._warnings_label.setText(
            ", ".join(warnings) if warnings else "(none)")

        self._timestamp.setText(
            f"Last updated: {status.get('timestamp', '')}")

    _LABELS = {
        "range_km": "\U0001F4CF Range",
        "total_range_km": "\U0001F4CF Total Range",
        "charge_status": "\u26A1 Charge Status",
        "plug_status": "\U0001F50C Plug",
        "charge_mode": "\u26A1 Charge Mode",
        "time_to_charge": "\u23F1 Time to Charge",
        "charge_limit_home": "\U0001F3E0 Limit (Home)",
        "charge_limit_away": "\U0001F30D Limit (Away)",
        "doors_locked": "\U0001F512 Doors",
        "all_doors_closed": "\U0001F6AA All Closed",
        "all_windows_closed": "\U0001FA9F Windows",
        "hood_open": "\U0001F527 Hood",
        "trunk_open": "\U0001F4E6 Trunk",
        "lights_on": "\U0001F4A1 Lights",
        "headlights": "\U0001F526 Headlights",
        "parking_lights": "\U0001F6A8 Parking Lights",
        "latitude": "\U0001F4CD Latitude",
        "longitude": "\U0001F4CD Longitude",
        "home_away": "\U0001F3E0 Home/Away",
        "speed_kmh": "\U0001F3CE Speed",
        "climate_active": "\u2744 Status",
        "cabin_temp_c": "\U0001F321 Cabin",
        "interior_temp_c": "\U0001F321 Interior",
        "odometer_km": "\U0001F4CF Odometer",
        "ignition": "\U0001F511 Ignition",
    }

    @classmethod
    def _nice_label(cls, key: str) -> str:
        return cls._LABELS.get(key, key.replace("_", " ").title())
