"""Dashboard widget showing vehicle status with integrated actions."""

from datetime import UTC, datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import t
from ..icons import icon, pixmap


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
    "range_climate_on": ("ruler", "dashboard.range_climate_on"),
    "range_climate_off": ("ruler", "dashboard.range_climate_off"),
    "total_range": ("ruler", "dashboard.total_range"),
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
    "speed": ("gauge", "dashboard.speed"),
    "climate_active": ("snowflake", "dashboard.status"),
    "cabin_temp": ("thermometer", "dashboard.cabin"),
    "interior_temp": ("thermometer", "dashboard.interior"),
    "ignition": ("key-round", "dashboard.ignition"),
}


class DashboardWidget(QWidget):
    def __init__(self, actions: dict = None):
        """
        Args:
            actions: dict of callback functions:
                on_lock, on_unlock, on_horn_lights,
                on_charge_start, on_charge_stop, on_charge_limit, on_charge_schedule,
                on_climate_start, on_climate_stop, on_climate_settings, on_climate_schedule,
                on_locate
        """
        super().__init__()
        self._actions = actions or {}
        self._labels = {}
        self._rows = {}  # field -> QHBoxLayout (for hiding rows)
        self._status = {}

        grid = QGridLayout(self)

        # Battery card
        bat_box, bat_layout = _card(t("dashboard.battery"), "battery-charging")
        self._battery_bar = QProgressBar()
        self._battery_bar.setRange(0, 100)
        self._battery_bar.setTextVisible(True)
        bat_layout.addWidget(self._battery_bar)
        for key in ("range_climate_on", "range_climate_off", "total_range", "charge_status",
                     "plug_status", "charge_mode", "time_to_charge",
                     "charge_limit_home", "charge_limit_away", "ignition"):
            icon_name, i18n_key = _FIELDS[key]
            h, val = _row(icon_name, t(i18n_key))
            bat_layout.addLayout(h)
            self._labels[key] = val
            self._rows[key] = h
        # Battery actions
        bat_actions = QHBoxLayout()
        self._charge_btn = QPushButton(icon("zap"), t("commands.charge_on"))
        self._charge_btn.clicked.connect(self._on_charge_toggle)
        bat_actions.addWidget(self._charge_btn)
        self._limit_btn = QPushButton(icon("battery-charging"), t("commands.charge_limit"))
        self._limit_btn.clicked.connect(lambda: self._call("on_charge_limit"))
        bat_actions.addWidget(self._limit_btn)
        self._charge_sched_btn = QPushButton(icon("calendar-clock"), t("schedules.charge"))
        self._charge_sched_btn.clicked.connect(lambda: self._call("on_charge_schedule"))
        bat_actions.addWidget(self._charge_sched_btn)
        bat_layout.addLayout(bat_actions)
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
            self._rows[key] = h
        # Security actions
        sec_actions = QHBoxLayout()
        self._lock_btn = QPushButton(icon("lock"), t("commands.lock"))
        self._lock_btn.clicked.connect(self._on_lock_toggle)
        sec_actions.addWidget(self._lock_btn)
        self._horn_btn = QPushButton(icon("megaphone"), t("commands.horn_lights"))
        self._horn_btn.clicked.connect(self._on_horn_lights)
        sec_actions.addWidget(self._horn_btn)
        sec_layout.addLayout(sec_actions)
        grid.addWidget(sec_box, 0, 1)

        # Location card
        loc_box, loc_layout = _card(t("dashboard.location"), "map-pin")
        loc_row = QHBoxLayout()
        loc_icon = QLabel()
        loc_icon.setPixmap(pixmap("map-pin", 14))
        loc_icon.setFixedWidth(20)
        loc_lbl = QLabel(t("dashboard.coordinates"))
        loc_lbl.setStyleSheet("color: gray;")
        self._location_link = QLabel("")
        self._location_link.setOpenExternalLinks(True)
        self._location_link.setTextFormat(Qt.TextFormat.RichText)
        self._location_link.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction)
        loc_row.addWidget(loc_icon)
        loc_row.addWidget(loc_lbl)
        loc_row.addStretch()
        loc_row.addWidget(self._location_link)
        loc_layout.addLayout(loc_row)
        for key in ("home_away", "speed"):
            icon_name, i18n_key = _FIELDS[key]
            h, val = _row(icon_name, t(i18n_key))
            loc_layout.addLayout(h)
            self._labels[key] = val
        # Location action
        loc_actions = QHBoxLayout()
        self._locate_btn = QPushButton(icon("map-pin"), t("commands.locate"))
        self._locate_btn.clicked.connect(lambda: self._call("on_locate"))
        loc_actions.addWidget(self._locate_btn)
        loc_actions.addStretch()
        loc_layout.addLayout(loc_actions)
        grid.addWidget(loc_box, 1, 0)

        # Climate card
        clim_box, clim_layout = _card(t("dashboard.climate"), "snowflake")
        for key in ("climate_active", "cabin_temp", "interior_temp"):
            icon_name, i18n_key = _FIELDS[key]
            h, val = _row(icon_name, t(i18n_key))
            clim_layout.addLayout(h)
            self._labels[key] = val
            self._rows[key] = h
        # Climate actions
        clim_actions = QHBoxLayout()
        self._climate_btn = QPushButton(icon("snowflake"), t("commands.climate_on"))
        self._climate_btn.clicked.connect(self._on_climate_toggle)
        clim_actions.addWidget(self._climate_btn)
        self._settings_btn = QPushButton(icon("settings"), t("commands.climate_settings"))
        self._settings_btn.clicked.connect(lambda: self._call("on_climate_settings"))
        clim_actions.addWidget(self._settings_btn)
        self._clim_sched_btn = QPushButton(icon("calendar-clock"), t("schedules.climate"))
        self._clim_sched_btn.clicked.connect(lambda: self._call("on_climate_schedule"))
        clim_actions.addWidget(self._clim_sched_btn)
        clim_layout.addLayout(clim_actions)
        grid.addWidget(clim_box, 1, 1)

        # Warnings card
        warn_box, warn_layout = _card(t("dashboard.warnings"), "triangle-alert")
        self._warnings_label = _selectable(QLabel(t("dashboard.no_warnings")))
        warn_layout.addWidget(self._warnings_label)
        grid.addWidget(warn_box, 2, 0, 1, 2)

        # All action buttons (for enabling/disabling during commands)
        self._action_buttons = [
            self._charge_btn, self._limit_btn, self._charge_sched_btn,
            self._lock_btn, self._horn_btn,
            self._locate_btn,
            self._climate_btn, self._settings_btn, self._clim_sched_btn,
        ]

        # Timestamp
        self._timestamp = _selectable(QLabel(""))
        self._timestamp.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._timestamp.setStyleSheet("color: gray; font-size: 11px;")
        grid.addWidget(self._timestamp, 3, 0, 1, 2)

    def _call(self, action_name: str):
        cb = self._actions.get(action_name)
        if cb:
            cb()

    def set_actions_enabled(self, enabled: bool):
        for btn in self._action_buttons:
            btn.setEnabled(enabled)

    def _on_lock_toggle(self):
        if self._status.get("doors_locked", False):
            # Currently locked -> unlock (needs confirmation)
            if QMessageBox.question(
                self, t("commands.confirm"),
                t("commands.confirm_action", action=t("commands.confirm_unlock")),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            ) == QMessageBox.StandardButton.Yes:
                self._call("on_unlock")
        else:
            self._call("on_lock")

    def _on_charge_toggle(self):
        status = self._status.get("charge_status", "")
        if status == "charging":
            self._call("on_charge_stop")
        else:
            self._call("on_charge_start")

    def _on_climate_toggle(self):
        if self._status.get("climate_active", False):
            self._call("on_climate_stop")
        else:
            self._call("on_climate_start")

    def _on_horn_lights(self):
        if QMessageBox.question(
            self, t("commands.confirm"),
            t("commands.confirm_action", action=t("commands.confirm_horn")),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self._call("on_horn_lights")

    def current_status(self) -> dict:
        return self._status

    def update_status(self, status: dict):
        self._status = status
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

        def _tv(v):
            """Translate an API value string, fall back to raw value."""
            key = f"dashboard.val.{str(v).lower()}"
            result = t(key)
            return result if result != key else str(v)

        dist = status.get("distance_unit", "km")
        spd = status.get("speed_unit", f"{dist}/h")
        temp = status.get("temp_unit", "c")
        temp_sym = "\u00b0F" if temp.lower() == "f" else "\u00b0C"

        formatters = {
            "range_climate_on": lambda v: f"{v} {dist}",
            "range_climate_off": lambda v: f"{v} {dist}",
            "total_range": lambda v: f"{v} {dist}",
            "charge_status": _tv,
            "plug_status": _tv,
            "charge_mode": _tv,
            "home_away": _tv,
            "ignition": _tv,
            "time_to_charge": lambda v: f"{v} min" if v else "\u2014",
            "charge_limit_home": lambda v: f"{v}%",
            "charge_limit_away": lambda v: f"{v}%",
            "doors_locked": lambda v: t("dashboard.locked") if v else t("dashboard.unlocked"),
            "all_doors_closed": lambda v: t("dashboard.closed") if v else t("dashboard.open"),
            "all_windows_closed": lambda v: t("dashboard.closed") if v else t("dashboard.open"),
            "hood_open": lambda v: t("dashboard.open") if v else t("dashboard.closed"),
            "trunk_open": lambda v: t("dashboard.open") if v else t("dashboard.closed"),
            "lights_on": lambda v: t("dashboard.on") if v else t("dashboard.off"),
            "headlights": lambda v: t("dashboard.on") if str(v).lower() == "on" else t("dashboard.off"),
            "parking_lights": lambda v: t("dashboard.on") if str(v).lower() == "on" else t("dashboard.off"),
            "climate_active": lambda v: t("dashboard.climate_on") if v else t("dashboard.climate_off"),
            "cabin_temp": lambda v: f"{v}{temp_sym}",
            "interior_temp": lambda v: f"{v}{temp_sym}",
            "speed": lambda v: f"{v} {spd}",
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

        # Update toggle buttons
        locked = status.get("doors_locked", False)
        if locked:
            self._lock_btn.setText(t("commands.unlock"))
            self._lock_btn.setIcon(icon("lock-open"))
        else:
            self._lock_btn.setText(t("commands.lock"))
            self._lock_btn.setIcon(icon("lock"))

        charge_status = status.get("charge_status", "")
        if charge_status == "charging":
            self._charge_btn.setText(t("commands.charge_off"))
            self._charge_btn.setIcon(icon("square"))
        else:
            self._charge_btn.setText(t("commands.charge_on"))
            self._charge_btn.setIcon(icon("zap"))

        if status.get("climate_active", False):
            self._climate_btn.setText(t("commands.climate_off"))
            self._climate_btn.setIcon(icon("circle-stop"))
        else:
            self._climate_btn.setText(t("commands.climate_on"))
            self._climate_btn.setIcon(icon("snowflake"))

        warnings = status.get("warning_lamps", [])
        self._warnings_label.setText(
            ", ".join(warnings) if warnings else t("dashboard.no_warnings"))

        ts_raw = status.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            ts_local = dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, AttributeError):
            ts_local = ts_raw
        self._timestamp.setText(
            t("dashboard.last_updated", timestamp=ts_local))

    @staticmethod
    def _set_row_visible(row: QHBoxLayout, visible: bool):
        for i in range(row.count()):
            widget = row.itemAt(i).widget()
            if widget:
                widget.setVisible(visible)

    def set_ui_config(self, ui_config):
        if ui_config is None:
            return
        if "all_windows_closed" in self._rows:
            self._set_row_visible(
                self._rows["all_windows_closed"],
                not getattr(ui_config, "hide_window_status", False))
        if "interior_temp" in self._rows:
            self._set_row_visible(
                self._rows["interior_temp"],
                not getattr(ui_config, "hide_internal_temperature", False))
        if getattr(ui_config, "hide_climate_settings", False):
            self._settings_btn.setVisible(False)

    def set_capabilities(self, caps):
        mapping = {
            "_charge_btn": "remote_charge",
            "_limit_btn": "max_charge",
            "_charge_sched_btn": "charge_schedule",
            "_lock_btn": "remote_lock",
            "_horn_btn": "remote_horn",
            "_locate_btn": "car_finder",
            "_climate_btn": "remote_climate",
            "_settings_btn": "remote_climate",
            "_clim_sched_btn": "climate_schedule",
        }
        for attr, field in mapping.items():
            getattr(self, attr).setVisible(getattr(caps, field, True))
