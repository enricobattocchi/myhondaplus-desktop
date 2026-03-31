"""Trip history and statistics widget."""

import csv
from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..i18n import t
from ..icons import icon, pixmap
from ..workers import TripsWorker


def _stat_card(icon_name: str, label: str, value: str = "") -> tuple[QVBoxLayout, QLabel]:
    layout = QVBoxLayout()
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon_lbl = QLabel()
    icon_lbl.setPixmap(pixmap(icon_name, 24))
    icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(icon_lbl)
    val_lbl = QLabel(value)
    val_lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
    val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    val_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    layout.addWidget(val_lbl)
    desc_lbl = QLabel(label)
    desc_lbl.setStyleSheet("color: gray; font-size: 11px;")
    desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(desc_lbl)
    return layout, val_lbl


class TripsWidget(QWidget):
    def __init__(self, get_api, get_vin, get_vehicles, on_status, on_error):
        super().__init__()
        self._get_api = get_api
        self._get_vin = get_vin
        self._get_vehicles = get_vehicles
        self._on_status = on_status
        self._on_error = on_error
        self._worker = None
        self._current_month = date.today().replace(day=1)
        self._trips_data = []
        self._last_consumption_unit = ""
        self._last_distance_unit = "km"
        self._last_speed_unit = "km/h"

        layout = QVBoxLayout(self)

        # Month selector
        month_bar = QHBoxLayout()
        prev_btn = QPushButton(icon("chevron-left"), "")
        prev_btn.setFixedWidth(32)
        prev_btn.clicked.connect(self._prev_month)
        month_bar.addStretch()
        month_bar.addWidget(prev_btn)
        self._month_label = QLabel(self._format_month())
        self._month_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self._month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._month_label.setMinimumWidth(150)
        month_bar.addWidget(self._month_label)
        next_btn = QPushButton(icon("chevron-right"), "")
        next_btn.setFixedWidth(32)
        next_btn.clicked.connect(self._next_month)
        month_bar.addWidget(next_btn)
        month_bar.addStretch()
        self._locations_cb = QCheckBox(t("trips.include_locations"))
        self._locations_cb.setToolTip(t("trips.locations_tooltip"))
        self._locations_cb.stateChanged.connect(self._on_locations_toggled)
        month_bar.addWidget(self._locations_cb)
        export_btn = QPushButton(icon("download"), t("trips.export_csv"))
        export_btn.clicked.connect(self._export_csv)
        month_bar.addWidget(export_btn)
        layout.addLayout(month_bar)

        # Stats row
        stats_box = QGroupBox("")
        stats_layout = QHBoxLayout(stats_box)

        self._stat_labels = {}
        stats = [
            ("route", t("trips.total_distance"), "trips"),
            ("bar-chart-2", t("trips.trip_count"), "count"),
            ("clock", t("trips.total_time"), "time"),
            ("gauge", t("trips.avg_speed"), "avg_speed"),
            ("gauge", t("trips.max_speed"), "max_speed"),
            ("fuel", t("trips.avg_consumption"), "consumption"),
        ]
        for icon_name, label, key in stats:
            s_layout, val_lbl = _stat_card(icon_name, label)
            stats_layout.addLayout(s_layout)
            self._stat_labels[key] = val_lbl

        layout.addWidget(stats_box)

        # Period label
        self._period_label = QLabel("")
        self._period_label.setStyleSheet("color: gray; font-size: 11px;")
        self._period_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._period_label)

        # Trip table
        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            t("trips.date"), t("trips.start"), t("trips.end"),
            t("trips.distance"), t("trips.duration"),
            t("trips.avg_speed"), t("trips.consumption"),
        ])
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

    def _format_month(self) -> str:
        return self._current_month.strftime("%B %Y")

    def _prev_month(self):
        m = self._current_month
        self._current_month = (m.replace(day=1) - date.resolution).replace(day=1)
        self._month_label.setText(self._format_month())
        self.load_trips()

    def _next_month(self):
        m = self._current_month
        if m.month == 12:
            self._current_month = m.replace(year=m.year + 1, month=1)
        else:
            self._current_month = m.replace(month=m.month + 1)
        self._month_label.setText(self._format_month())
        self.load_trips()

    def _on_cell_double_clicked(self, row: int, col: int):
        item = self._table.item(row, col)
        if item:
            url = item.data(Qt.ItemDataRole.UserRole)
            if url:
                from PyQt6.QtCore import QUrl
                from PyQt6.QtGui import QDesktopServices
                QDesktopServices.openUrl(QUrl(url))

    def _on_locations_toggled(self, state):
        if self._trips_data:
            self.load_trips()

    def _consumption_unit(self) -> str:
        vin = self._get_vin()
        for v in self._get_vehicles():
            if v["vin"] == vin and v.get("fuel_type") == "E":
                return "kWh/100km"
        return "L/100km"

    def load_trips(self):
        api = self._get_api()
        vin = self._get_vin()
        if not vin:
            return
        month_start = self._current_month.strftime("%Y-%m-%dT00:00:00.000Z")
        self._worker = TripsWorker(
            api, vin, month_start=month_start,
            include_locations=self._locations_cb.isChecked())
        self._worker.finished.connect(self._on_trips_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.progress.connect(self._on_status)
        self._worker.start()

    def _export_csv(self):
        if not self._trips_data:
            self._on_error(t("trips.no_trips_export"))
            return
        vin = self._get_vin()
        default_name = f"trips-{vin}-{self._current_month.strftime('%Y-%m')}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, t("trips.export_title"), default_name, t("trips.csv_filter"))
        if not path:
            return
        unit = self._last_consumption_unit or self._consumption_unit()
        has_locs = any("start_lat" in t for t in self._trips_data)
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            header = [
                "Date", "Start", "End",
                f"Distance ({self._last_distance_unit})", "Duration (min)",
                f"Avg Speed ({self._last_speed_unit})",
                f"Max Speed ({self._last_speed_unit})",
                f"Consumption ({unit})",
            ]
            if has_locs:
                header.extend([
                    "Start Lat", "Start Lon", "End Lat", "End Lon"])
            writer.writerow(header)
            for trip in self._trips_data:
                row = [
                    trip.get("OneTripDate", "")[:10],
                    trip.get("StartTime", ""),
                    trip.get("EndTime", ""),
                    trip.get("Mileage", ""),
                    trip.get("DriveTime", ""),
                    trip.get("AveSpeed", ""),
                    trip.get("MaxSpeed", ""),
                    trip.get("AveFuelEconomy", ""),
                ]
                if has_locs:
                    row.extend([
                        trip.get("start_lat", ""),
                        trip.get("start_lon", ""),
                        trip.get("end_lat", ""),
                        trip.get("end_lon", ""),
                    ])
                writer.writerow(row)
        self._on_status(t("trips.exported", count=len(self._trips_data), path=path))

    def _on_trips_loaded(self, data: dict):
        trips = data["trips"]
        stats = data["stats"]
        self._trips_data = trips
        if stats:
            self._last_consumption_unit = stats.get("consumption_unit", self._consumption_unit())
            self._last_distance_unit = stats.get("distance_unit", "km")
            self._last_speed_unit = stats.get("speed_unit", "km/h")

        # Update stats
        if stats:
            dist = stats.get("distance_unit", "km")
            spd = stats.get("speed_unit", f"{dist}/h")
            self._stat_labels["trips"].setText(f"{stats['total_distance']} {dist}")
            self._stat_labels["count"].setText(str(stats["trips"]))
            hours = int(stats["total_minutes"]) // 60
            mins = int(stats["total_minutes"]) % 60
            self._stat_labels["time"].setText(f"{hours}h {mins}min")
            self._stat_labels["avg_speed"].setText(f"{stats['avg_speed']} {spd}")
            self._stat_labels["max_speed"].setText(f"{stats['max_speed']} {spd}")
            self._stat_labels["consumption"].setText(
                f"{stats['avg_consumption']} {stats['consumption_unit']}")
            self._period_label.setText(
                f"{stats['start_date']} \u2014 {stats['end_date']}")
        else:
            for lbl in self._stat_labels.values():
                lbl.setText("\u2014")
            self._period_label.setText(t("trips.no_trips"))

        # Check if trips have location data
        has_locs = any("start_lat" in t for t in trips)

        # Update table columns
        unit = self._last_consumption_unit or self._consumption_unit()
        headers = [
            t("trips.date"), t("trips.start"), t("trips.end"),
            t("trips.distance"), t("trips.duration"),
            t("trips.avg_speed"), t("trips.consumption"),
        ]
        if has_locs:
            headers.extend([t("trips.from"), t("trips.to")])
        self._table.setColumnCount(len(headers))
        self._table.setHorizontalHeaderLabels(headers)

        self._table.setRowCount(len(trips))
        for i, trip in enumerate(trips):
            start = trip.get("StartTime", "")
            end = trip.get("EndTime", "")
            start_time = start.split("T")[1][:5] if "T" in start else start
            end_time = end.split("T")[1][:5] if "T" in end else end

            items = [
                trip.get("OneTripDate", "")[:10],
                start_time,
                end_time,
                f"{trip.get('Mileage', '?')} {self._last_distance_unit}",
                f"{trip.get('DriveTime', '?')} min",
                f"{trip.get('AveSpeed', '?')} {self._last_speed_unit}",
                f"{trip.get('AveFuelEconomy', '?')} {unit}",
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(str(text))
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    if col >= 3 else
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self._table.setItem(i, col, item)

            if has_locs:
                from PyQt6.QtGui import QColor
                # Use a bright cyan that works on both light and dark
                link_color = QColor(80, 180, 255)
                base_col = len(items)
                for offset, prefix in enumerate(["start", "end"]):
                    lat = trip.get(f"{prefix}_lat", "")
                    lon = trip.get(f"{prefix}_lon", "")
                    item = QTableWidgetItem(
                        f"{lat}, {lon}" if lat else "")
                    if lat and lon:
                        url = (f"https://www.openstreetmap.org/"
                               f"?mlat={lat}&mlon={lon}#map=17/{lat}/{lon}")
                        item.setData(Qt.ItemDataRole.UserRole, url)
                        item.setForeground(link_color)
                        item.setToolTip(t("trips.location_tooltip"))
                    self._table.setItem(i, base_col + offset, item)

        self._on_status(t("trips.loaded"))
