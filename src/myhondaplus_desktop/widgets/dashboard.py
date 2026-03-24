"""Dashboard widget showing vehicle status."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QProgressBar, QFrame,
)
from PyQt6.QtCore import Qt

from ..icons import pixmap
from ..i18n import t


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
    header = QHBoxLayout()
    icon_lbl = QLabel()
    icon_lbl.setPixmap(pixmap(icon_name, 20))
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
    header.addWidget(icon_lbl)
    header.addWidget(title_lbl)
    header.addStretch()
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


# Maps field keys to (icon_name, i18n_key)
_FIELDS = {
    "range_km": ("ruler", "dashboard.range"),
    "total_range_km": ("ruler", "dashboard.total_range"),
    "charge_status": ("zap", "dashboard.charge_status"),
    "plug_status": ("plug", "dashboard.plug"),
    "charge_mode": ("zap", "dashboard.charge_mode"),
    "time_to_charge": ("timer", "dashboard.time_to_charge"),
    "charge_limit_home": ("house", "dashboard.limit_home"),
    "charge_limit_away": ("globe", "dashboard.limit_away"),
    "doors_locked": ("lock", "dashboard.doors"),
    "all_doors_closed": ("door-open", "dashboard.all_closed"),
    "all_windows_closed": ("app-window", "dashboard.windows"),
    "hood_open": ("wrench", "dashboard.hood"),
    "trunk_open": ("package", "dashboard.trunk"),
    "lights_on": ("lightbulb", "dashboard.lights"),
    "headlights": ("flashlight", "dashboard.headlights"),
    "parking_lights": ("siren", "dashboard.parking_lights"),
    "home_away": ("house", "dashboard.home_away"),
    "speed_kmh": ("gauge", "dashboard.speed"),
    "climate_active": ("snowflake", "dashboard.status"),
    "cabin_temp_c": ("thermometer", "dashboard.cabin"),
    "interior_temp_c": ("thermometer", "dashboard.interior"),
    "odometer_km": ("milestone", "dashboard.odometer"),
    "ignition": ("key-round", "dashboard.ignition"),
}


class DashboardWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._labels = {}

        grid = QGridLayout(self)

        # Battery card
        bat_box, bat_layout = _card(t("dashboard.battery"), "battery-charging")
        self._battery_bar = QProgressBar()
        self._battery_bar.setRange(0, 100)
        self._battery_bar.setTextVisible(True)
        bat_layout.addWidget(self._battery_bar)
        for key in ("range_km", "total_range_km", "charge_status",
                     "plug_status", "charge_mode", "time_to_charge",
                     "charge_limit_home", "charge_limit_away"):
            icon_name, i18n_key = _FIELDS[key]
            h, val = _row(icon_name, t(i18n_key))
            bat_layout.addLayout(h)
            self._labels[key] = val
        grid.addWidget(bat_box, 0, 0)

        # Security card
        sec_box, sec_layout = _card(t("dashboard.security"), "shield")
        for key in ("doors_locked", "all_doors_closed", "all_windows_closed",
                     "hood_open", "trunk_open", "lights_on",
                     "headlights", "parking_lights"):
            icon_name, i18n_key = _FIELDS[key]
            h, val = _row(icon_name, t(i18n_key))
            sec_layout.addLayout(h)
            self._labels[key] = val
        grid.addWidget(sec_box, 0, 1)

        # Location card
        loc_box, loc_layout = _card(t("dashboard.location"), "map-pin")
        self._location_link = QLabel("")
        self._location_link.setOpenExternalLinks(True)
        self._location_link.setTextFormat(Qt.TextFormat.RichText)
        self._location_link.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction)
        loc_layout.addWidget(self._location_link)
        for key in ("home_away", "speed_kmh"):
            icon_name, i18n_key = _FIELDS[key]
            h, val = _row(icon_name, t(i18n_key))
            loc_layout.addLayout(h)
            self._labels[key] = val
        grid.addWidget(loc_box, 1, 0)

        # Climate card
        clim_box, clim_layout = _card(t("dashboard.climate"), "snowflake")
        for key in ("climate_active", "cabin_temp_c", "interior_temp_c"):
            icon_name, i18n_key = _FIELDS[key]
            h, val = _row(icon_name, t(i18n_key))
            clim_layout.addLayout(h)
            self._labels[key] = val
        grid.addWidget(clim_box, 1, 1)

        # Vehicle card
        veh_box, veh_layout = _card(t("dashboard.vehicle"), "car")
        h, val = _row("clipboard", t("dashboard.vin"))
        veh_layout.addLayout(h)
        self._vin_label = val
        for key in ("odometer_km", "ignition"):
            icon_name, i18n_key = _FIELDS[key]
            h, val = _row(icon_name, t(i18n_key))
            veh_layout.addLayout(h)
            self._labels[key] = val
        grid.addWidget(veh_box, 2, 0)

        # Warnings card
        warn_box, warn_layout = _card(t("dashboard.warnings"), "triangle-alert")
        self._warnings_label = _selectable(QLabel(t("dashboard.no_warnings")))
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
            self._location_link.setText(t("dashboard.unknown"))

        formatters = {
            "range_km": lambda v: f"{v} km",
            "total_range_km": lambda v: f"{v} km",
            "time_to_charge": lambda v: f"{v} min" if v else "\u2014",
            "charge_limit_home": lambda v: f"{v}%",
            "charge_limit_away": lambda v: f"{v}%",
            "doors_locked": lambda v: t("dashboard.locked") if v else t("dashboard.unlocked"),
            "all_doors_closed": lambda v: t("dashboard.yes") if v else t("dashboard.no"),
            "all_windows_closed": lambda v: t("dashboard.yes") if v else t("dashboard.no"),
            "hood_open": lambda v: t("dashboard.open") if v else t("dashboard.closed"),
            "trunk_open": lambda v: t("dashboard.open") if v else t("dashboard.closed"),
            "lights_on": lambda v: t("dashboard.on") if v else t("dashboard.off"),
            "climate_active": lambda v: t("dashboard.climate_on") if v else t("dashboard.climate_off"),
            "cabin_temp_c": lambda v: f"{v}\u00b0C",
            "interior_temp_c": lambda v: f"{v}\u00b0C",
            "odometer_km": lambda v: f"{v:,} km",
            "speed_kmh": lambda v: f"{v} km/h",
        }

        for key, label in self._labels.items():
            value = status.get(key, "")
            fmt = formatters.get(key)
            label.setText(fmt(value) if fmt else str(value))

        if "doors_locked" in self._labels:
            locked = status.get("doors_locked", False)
            self._labels["doors_locked"].setStyleSheet(
                "color: green; font-weight: bold;" if locked
                else "color: red; font-weight: bold;")

        warnings = status.get("warning_lamps", [])
        self._warnings_label.setText(
            ", ".join(warnings) if warnings else t("dashboard.no_warnings"))

        self._timestamp.setText(
            t("dashboard.last_updated", timestamp=status.get("timestamp", "")))
