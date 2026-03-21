"""Dashboard widget showing vehicle status."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QProgressBar, QFrame,
)
from PyQt6.QtCore import Qt

from ..icons import pixmap


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


def _card(title: str, icon_name: str) -> tuple[QGroupBox, QVBoxLayout]:
    box = QGroupBox(title)
    box.setStyleSheet("QGroupBox { font-weight: bold; }")
    layout = QVBoxLayout(box)
    # Add icon to the title via a header row
    header = QHBoxLayout()
    icon_lbl = QLabel()
    icon_lbl.setPixmap(pixmap(icon_name, 20))
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
    header.addWidget(icon_lbl)
    header.addWidget(title_lbl)
    header.addStretch()
    # Clear the QGroupBox title since we use our own header
    box.setTitle("")
    layout.addLayout(header)
    return box, layout


def _selectable(label: QLabel) -> QLabel:
    """Make a QLabel's text selectable by mouse."""
    label.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setCursor(Qt.CursorShape.IBeamCursor)
    return label


def _row(icon_name: str, label: str, value: str = "") -> tuple[QHBoxLayout, QLabel]:
    h = QHBoxLayout()
    icon_lbl = QLabel()
    icon_lbl.setPixmap(pixmap(icon_name, 14))
    icon_lbl.setFixedWidth(20)
    lbl = QLabel(label)
    lbl.setStyleSheet("color: gray;")
    val = _selectable(QLabel(value))
    h.addWidget(icon_lbl)
    h.addWidget(lbl)
    h.addStretch()
    h.addWidget(val)
    return h, val


# Maps field keys to (icon_name, display_label)
_FIELDS = {
    "range_km": ("ruler", "Range"),
    "total_range_km": ("ruler", "Total Range"),
    "charge_status": ("zap", "Charge Status"),
    "plug_status": ("plug", "Plug"),
    "charge_mode": ("zap", "Charge Mode"),
    "time_to_charge": ("timer", "Time to Charge"),
    "charge_limit_home": ("house", "Limit (Home)"),
    "charge_limit_away": ("globe", "Limit (Away)"),
    "doors_locked": ("lock", "Doors"),
    "all_doors_closed": ("door-open", "All Closed"),
    "all_windows_closed": ("app-window", "Windows"),
    "hood_open": ("wrench", "Hood"),
    "trunk_open": ("package", "Trunk"),
    "lights_on": ("lightbulb", "Lights"),
    "headlights": ("flashlight", "Headlights"),
    "parking_lights": ("siren", "Parking Lights"),
    "home_away": ("house", "Home/Away"),
    "speed_kmh": ("gauge", "Speed"),
    "climate_active": ("snowflake", "Status"),
    "cabin_temp_c": ("thermometer", "Cabin"),
    "interior_temp_c": ("thermometer", "Interior"),
    "odometer_km": ("milestone", "Odometer"),
    "ignition": ("key-round", "Ignition"),
}


class DashboardWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._labels = {}

        grid = QGridLayout(self)

        # Battery card
        bat_box, bat_layout = _card("Battery", "battery-charging")
        self._battery_bar = QProgressBar()
        self._battery_bar.setRange(0, 100)
        self._battery_bar.setTextVisible(True)
        bat_layout.addWidget(self._battery_bar)
        for key in ("range_km", "total_range_km", "charge_status",
                     "plug_status", "charge_mode", "time_to_charge",
                     "charge_limit_home", "charge_limit_away"):
            icon_name, label = _FIELDS[key]
            h, val = _row(icon_name, label)
            bat_layout.addLayout(h)
            self._labels[key] = val
        grid.addWidget(bat_box, 0, 0)

        # Security card
        sec_box, sec_layout = _card("Security", "shield")
        for key in ("doors_locked", "all_doors_closed", "all_windows_closed",
                     "hood_open", "trunk_open", "lights_on",
                     "headlights", "parking_lights"):
            icon_name, label = _FIELDS[key]
            h, val = _row(icon_name, label)
            sec_layout.addLayout(h)
            self._labels[key] = val
        grid.addWidget(sec_box, 0, 1)

        # Location card
        loc_box, loc_layout = _card("Location", "map-pin")
        self._location_link = QLabel("")
        self._location_link.setOpenExternalLinks(True)
        self._location_link.setTextFormat(Qt.TextFormat.RichText)
        self._location_link.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction)
        loc_layout.addWidget(self._location_link)
        for key in ("home_away", "speed_kmh"):
            icon_name, label = _FIELDS[key]
            h, val = _row(icon_name, label)
            loc_layout.addLayout(h)
            self._labels[key] = val
        grid.addWidget(loc_box, 1, 0)

        # Climate card
        clim_box, clim_layout = _card("Climate", "snowflake")
        for key in ("climate_active", "cabin_temp_c", "interior_temp_c"):
            icon_name, label = _FIELDS[key]
            h, val = _row(icon_name, label)
            clim_layout.addLayout(h)
            self._labels[key] = val
        grid.addWidget(clim_box, 1, 1)

        # Vehicle card
        veh_box, veh_layout = _card("Vehicle", "car")
        h, val = _row("clipboard", "VIN")
        veh_layout.addLayout(h)
        self._vin_label = val
        for key in ("odometer_km", "ignition"):
            icon_name, label = _FIELDS[key]
            h, val = _row(icon_name, label)
            veh_layout.addLayout(h)
            self._labels[key] = val
        grid.addWidget(veh_box, 2, 0)

        # Warnings card
        warn_box, warn_layout = _card("Warnings", "triangle-alert")
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
            "time_to_charge": lambda v: f"{v} min" if v else "\u2014",
            "charge_limit_home": lambda v: f"{v}%",
            "charge_limit_away": lambda v: f"{v}%",
            "doors_locked": lambda v: "Locked" if v else "UNLOCKED",
            "all_doors_closed": lambda v: "Yes" if v else "NO",
            "all_windows_closed": lambda v: "Yes" if v else "NO",
            "hood_open": lambda v: "Open" if v else "Closed",
            "trunk_open": lambda v: "Open" if v else "Closed",
            "lights_on": lambda v: "On" if v else "Off",
            "climate_active": lambda v: "ON" if v else "Off",
            "cabin_temp_c": lambda v: f"{v}\u00b0C",
            "interior_temp_c": lambda v: f"{v}\u00b0C",
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
