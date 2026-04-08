"""Schedule management dialogs for climate and charge prohibition."""

from PyQt6.QtCore import Qt, QTime
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTimeEdit,
    QVBoxLayout,
)

from ..i18n import t

DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _day_label(day_key: str) -> str:
    return t(f"schedules.{day_key}")


def _days_display(days: list[str]) -> str:
    return ", ".join(_day_label(d) for d in days) if days else ""


class ClimateSlotDialog(QDialog):
    """Edit a climate schedule slot (days + start time)."""

    def __init__(self, parent=None, slot_data: dict = None):
        super().__init__(parent)
        self.setWindowTitle(t("schedules.climate"))
        layout = QFormLayout(self)

        self._day_checks = {}
        days_layout = QHBoxLayout()
        existing_days = (slot_data or {}).get("days", [])
        for day in DAY_KEYS:
            cb = QCheckBox(_day_label(day))
            cb.setChecked(day in existing_days)
            days_layout.addWidget(cb)
            self._day_checks[day] = cb
        layout.addRow(t("schedules.days"), days_layout)

        self._time = QTimeEdit()
        start = (slot_data or {}).get("start_time", "07:00")
        h, m = start.split(":")
        self._time.setTime(QTime(int(h), int(m)))
        self._time.setDisplayFormat("HH:mm")
        layout.addRow(t("schedules.time"), self._time)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    @property
    def days(self) -> list[str]:
        return [d for d, cb in self._day_checks.items() if cb.isChecked()]

    @property
    def start_time(self) -> str:
        return self._time.time().toString("HH:mm")


class ChargeRuleDialog(QDialog):
    """Edit a charge prohibition rule (days + start/end time + location)."""

    def __init__(self, parent=None, rule_data: dict = None):
        super().__init__(parent)
        self.setWindowTitle(t("schedules.charge"))
        layout = QFormLayout(self)

        self._day_checks = {}
        days_layout = QHBoxLayout()
        existing_days = (rule_data or {}).get("days", [])
        for day in DAY_KEYS:
            cb = QCheckBox(_day_label(day))
            cb.setChecked(day in existing_days)
            days_layout.addWidget(cb)
            self._day_checks[day] = cb
        layout.addRow(t("schedules.days"), days_layout)

        self._start = QTimeEdit()
        start = (rule_data or {}).get("start_time", "23:00")
        h, m = start.split(":")
        self._start.setTime(QTime(int(h), int(m)))
        self._start.setDisplayFormat("HH:mm")
        layout.addRow(t("schedules.start_time"), self._start)

        self._end = QTimeEdit()
        end = (rule_data or {}).get("end_time", "06:00")
        h, m = end.split(":")
        self._end.setTime(QTime(int(h), int(m)))
        self._end.setDisplayFormat("HH:mm")
        layout.addRow(t("schedules.end_time"), self._end)

        self._location = QComboBox()
        self._location.addItem(t("schedules.location_all"), "all")
        self._location.addItem(t("schedules.location_home"), "home")
        current_loc = (rule_data or {}).get("location", "all")
        idx = self._location.findData(current_loc)
        if idx >= 0:
            self._location.setCurrentIndex(idx)
        layout.addRow(t("schedules.location"), self._location)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    @property
    def days(self) -> list[str]:
        return [d for d, cb in self._day_checks.items() if cb.isChecked()]

    @property
    def start_time(self) -> str:
        return self._start.time().toString("HH:mm")

    @property
    def end_time(self) -> str:
        return self._end.time().toString("HH:mm")

    @property
    def location(self) -> str:
        return self._location.currentData()


class ClimateSettingsDialog(QDialog):
    """Edit global climate settings (temp, duration, defrost)."""

    def __init__(self, parent=None, temp="normal", duration=30, defrost=True):
        super().__init__(parent)
        self.setWindowTitle(t("schedules.climate_settings"))
        self._saving = False
        self._layout = QFormLayout(self)

        self._temp = QComboBox()
        for val, key in [("cooler", "commands.cooler"), ("normal", "commands.normal"),
                         ("hotter", "commands.hotter")]:
            self._temp.addItem(t(key), val)
        idx = self._temp.findData(temp)
        if idx >= 0:
            self._temp.setCurrentIndex(idx)
        self._layout.addRow(t("commands.temperature"), self._temp)

        self._duration = QComboBox()
        for d in [10, 20, 30]:
            self._duration.addItem(f"{d}", d)
        idx = self._duration.findData(duration)
        if idx >= 0:
            self._duration.setCurrentIndex(idx)
        self._layout.addRow(t("commands.duration"), self._duration)

        self._defrost = QCheckBox(t("schedules.defrost"))
        self._defrost.setChecked(defrost)
        self._layout.addRow(self._defrost)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: gray; font-style: italic;")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setVisible(False)
        self._layout.addRow(self._status_label)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        self._layout.addRow(self._buttons)

    def set_accept_handler(self, handler):
        self._buttons.accepted.disconnect()
        self._buttons.accepted.connect(handler)

    def set_saving(self, saving: bool, message: str = ""):
        self._saving = saving
        self._buttons.setEnabled(not saving)
        self._temp.setEnabled(not saving)
        self._duration.setEnabled(not saving)
        self._defrost.setEnabled(not saving)
        self._status_label.setText(message)
        self._status_label.setVisible(bool(message))

    def reject(self):
        if not self._saving:
            super().reject()

    @property
    def temp(self) -> str:
        return self._temp.currentData()

    @property
    def duration(self) -> int:
        return self._duration.currentData()

    @property
    def defrost(self) -> bool:
        return self._defrost.isChecked()


class ChargeLimitDialog(QDialog):
    """Set charge limits for home and away."""

    LIMITS = [80, 85, 90, 95, 100]

    def __init__(self, parent=None, home: int = 80, away: int = 90):
        super().__init__(parent)
        self.setWindowTitle(t("commands.charge_limit"))
        self._saving = False
        self._layout = QFormLayout(self)

        self._home = QComboBox()
        for v in self.LIMITS:
            self._home.addItem(f"{v}%", v)
        idx = self._home.findData(home)
        if idx >= 0:
            self._home.setCurrentIndex(idx)
        self._layout.addRow(t("commands.home"), self._home)

        self._away = QComboBox()
        for v in self.LIMITS:
            self._away.addItem(f"{v}%", v)
        idx = self._away.findData(away)
        if idx >= 0:
            self._away.setCurrentIndex(idx)
        self._layout.addRow(t("commands.away"), self._away)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: gray; font-style: italic;")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setVisible(False)
        self._layout.addRow(self._status_label)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        self._layout.addRow(self._buttons)

    def set_accept_handler(self, handler):
        self._buttons.accepted.disconnect()
        self._buttons.accepted.connect(handler)

    @property
    def home(self) -> int:
        return self._home.currentData()

    @property
    def away(self) -> int:
        return self._away.currentData()

    def set_saving(self, saving: bool, message: str = ""):
        self._saving = saving
        self._buttons.setEnabled(not saving)
        self._home.setEnabled(not saving)
        self._away.setEnabled(not saving)
        self._status_label.setText(message)
        self._status_label.setVisible(bool(message))

    def reject(self):
        if not self._saving:
            super().reject()


class ClimateScheduleDialog(QDialog):
    """View and manage climate schedule slots."""

    def __init__(self, parent=None, schedule=None,
                 on_save=None, on_clear=None):
        super().__init__(parent)
        self.setWindowTitle(t("schedules.climate"))
        self.setMinimumWidth(450)
        self._schedule = list(schedule or [])
        while len(self._schedule) < 7:
            self._schedule.append({"enabled": False})
        self._on_save = on_save
        self._on_clear = on_clear
        self._saving = False

        self._layout = QVBoxLayout(self)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: gray; font-style: italic;")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setVisible(False)
        self._layout.addWidget(self._status_label)

        self._rows = []
        for i in range(7):
            row = self._make_row(i)
            self._layout.addLayout(row["layout"])
            self._rows.append(row)

        self._update_rows()

        btns = QHBoxLayout()
        btns.addStretch()
        self._clear_btn = QPushButton(t("schedules.clear_all"))
        self._clear_btn.clicked.connect(self._clear_all)
        btns.addWidget(self._clear_btn)
        self._layout.addLayout(btns)

        self._close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._close_box.rejected.connect(self.accept)
        self._layout.addWidget(self._close_box)

    def set_saving(self, saving: bool, message: str = ""):
        self._saving = saving
        self._close_box.setEnabled(not saving)
        self._clear_btn.setEnabled(not saving)
        for row in self._rows:
            row["button"].setEnabled(not saving)
        self._status_label.setText(message)
        self._status_label.setVisible(bool(message))

    def reject(self):
        if not self._saving:
            super().reject()

    def _make_row(self, index: int) -> dict:
        h = QHBoxLayout()
        num = QLabel(f"{index + 1}.")
        num.setFixedWidth(20)
        num.setStyleSheet("color: gray;")
        h.addWidget(num)
        label = QPushButton(t("schedules.not_set"))
        label.setFlat(True)
        label.setCursor(Qt.CursorShape.PointingHandCursor)
        label.setStyleSheet("text-align: left; padding: 4px;")
        label.clicked.connect(lambda checked, i=index: self._edit_slot(i))
        h.addWidget(label)
        return {"layout": h, "button": label}

    def _update_rows(self):
        for i, row in enumerate(self._rows):
            rule = self._schedule[i]
            if rule.get("enabled"):
                days = _days_display(rule["days"])
                row["button"].setText(f"{days}  {rule['start_time']}")
                row["button"].setStyleSheet("text-align: left; padding: 4px;")
            else:
                row["button"].setText(t("schedules.not_set"))
                row["button"].setStyleSheet("text-align: left; padding: 4px; color: gray;")

    def _edit_slot(self, idx: int):
        existing = None
        if self._schedule[idx].get("enabled"):
            existing = self._schedule[idx]
        dlg = ClimateSlotDialog(self, slot_data=existing)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if dlg.days:
            self._schedule[idx] = {
                "enabled": True, "days": dlg.days, "start_time": dlg.start_time}
        else:
            self._schedule[idx] = {"enabled": False}
        self._update_rows()
        if self._on_save:
            self._on_save(self._schedule)

    def _clear_all(self):
        if QMessageBox.question(
            self, t("schedules.clear_all"), t("schedules.clear_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._schedule = [{"enabled": False} for _ in range(7)]
        self._update_rows()
        if self._on_clear:
            self._on_clear()


class ChargeScheduleDialog(QDialog):
    """View and manage charge prohibition schedule."""

    def __init__(self, parent=None, schedule=None,
                 on_save=None, on_clear=None):
        super().__init__(parent)
        self.setWindowTitle(t("schedules.charge"))
        self.setMinimumWidth(450)
        self._schedule = list(schedule or [])
        while len(self._schedule) < 2:
            self._schedule.append({"enabled": False})
        self._on_save = on_save
        self._on_clear = on_clear
        self._saving = False

        self._layout = QVBoxLayout(self)

        note = QLabel(t("schedules.charge_note"))
        note.setStyleSheet("color: gray; font-style: italic;")
        note.setWordWrap(True)
        self._layout.addWidget(note)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: gray; font-style: italic;")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setVisible(False)
        self._layout.addWidget(self._status_label)

        self._rows = []
        for i in range(2):
            row = self._make_row(i)
            self._layout.addLayout(row["layout"])
            self._rows.append(row)

        self._update_rows()

        btns = QHBoxLayout()
        btns.addStretch()
        self._clear_btn = QPushButton(t("schedules.clear_all"))
        self._clear_btn.clicked.connect(self._clear_all)
        btns.addWidget(self._clear_btn)
        self._layout.addLayout(btns)

        self._close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._close_box.rejected.connect(self.accept)
        self._layout.addWidget(self._close_box)

    def set_saving(self, saving: bool, message: str = ""):
        self._saving = saving
        self._close_box.setEnabled(not saving)
        self._clear_btn.setEnabled(not saving)
        for row in self._rows:
            row["button"].setEnabled(not saving)
        self._status_label.setText(message)
        self._status_label.setVisible(bool(message))

    def reject(self):
        if not self._saving:
            super().reject()

    def _make_row(self, index: int) -> dict:
        h = QHBoxLayout()
        num = QLabel(f"{index + 1}.")
        num.setFixedWidth(20)
        num.setStyleSheet("color: gray;")
        h.addWidget(num)
        label = QPushButton(t("schedules.not_set"))
        label.setFlat(True)
        label.setCursor(Qt.CursorShape.PointingHandCursor)
        label.setStyleSheet("text-align: left; padding: 4px;")
        label.clicked.connect(lambda checked, i=index: self._edit_rule(i))
        h.addWidget(label)
        return {"layout": h, "button": label}

    def _update_rows(self):
        for i, row in enumerate(self._rows):
            rule = self._schedule[i]
            if rule.get("enabled"):
                days = _days_display(rule["days"])
                loc = t(f"schedules.location_{rule.get('location', 'all')}")
                row["button"].setText(
                    f"{days}  {rule['start_time']}\u2013{rule['end_time']}  ({loc})")
                row["button"].setStyleSheet("text-align: left; padding: 4px;")
            else:
                row["button"].setText(t("schedules.not_set"))
                row["button"].setStyleSheet("text-align: left; padding: 4px; color: gray;")

    def _edit_rule(self, idx: int):
        existing = None
        if self._schedule[idx].get("enabled"):
            existing = self._schedule[idx]
        dlg = ChargeRuleDialog(self, rule_data=existing)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if dlg.days:
            self._schedule[idx] = {
                "enabled": True, "days": dlg.days, "location": dlg.location,
                "start_time": dlg.start_time, "end_time": dlg.end_time}
        else:
            self._schedule[idx] = {"enabled": False}
        self._update_rows()
        if self._on_save:
            self._on_save(self._schedule)

    def _clear_all(self):
        if QMessageBox.question(
            self, t("schedules.clear_all"), t("schedules.clear_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        self._schedule = [{"enabled": False} for _ in range(2)]
        self._update_rows()
        if self._on_clear:
            self._on_clear()
