"""Command buttons panel."""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QMessageBox,
    QDialog, QFormLayout, QComboBox, QSpinBox, QDialogButtonBox,
)

from ..workers import CommandWorker
from pymyhondaplus import HondaAPI


class ClimateSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Climate Settings")
        layout = QFormLayout(self)

        self.temp_combo = QComboBox()
        self.temp_combo.addItems(["cooler", "normal", "hotter"])
        self.temp_combo.setCurrentText("normal")
        layout.addRow("Temperature:", self.temp_combo)

        self.duration_combo = QComboBox()
        self.duration_combo.addItems(["10", "20", "30"])
        self.duration_combo.setCurrentText("30")
        layout.addRow("Duration (min):", self.duration_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    @property
    def temp(self) -> str:
        return self.temp_combo.currentText()

    @property
    def duration(self) -> int:
        return int(self.duration_combo.currentText())


class ChargeLimitDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Charge Limits")
        layout = QFormLayout(self)

        self.home_spin = QSpinBox()
        self.home_spin.setRange(50, 100)
        self.home_spin.setValue(80)
        self.home_spin.setSuffix("%")
        layout.addRow("Home:", self.home_spin)

        self.away_spin = QSpinBox()
        self.away_spin.setRange(50, 100)
        self.away_spin.setValue(90)
        self.away_spin.setSuffix("%")
        layout.addRow("Away:", self.away_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)


class CommandsWidget(QWidget):
    def __init__(self, get_api, get_vin, on_progress, on_finished, on_error):
        super().__init__()
        self._get_api = get_api
        self._get_vin = get_vin
        self._on_progress = on_progress
        self._on_finished = on_finished
        self._on_error = on_error
        self._worker = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        buttons = [
            ("\U0001F512 Lock", self._lock),
            ("\U0001F513 Unlock", self._unlock),
            ("\u2744 Climate On", self._climate_start),
            ("\u26D4 Climate Off", self._climate_stop),
            ("\u2699 Climate Settings", self._climate_settings),
            ("\u26A1 Charge On", self._charge_start),
            ("\u23F9 Charge Off", self._charge_stop),
            ("\U0001F50B Charge Limit", self._charge_limit),
            ("\U0001F4EF Horn + Lights", self._horn_lights),
            ("\U0001F4CD Locate", self._locate),
        ]

        for label, handler in buttons:
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            layout.addWidget(btn)

    def _confirm(self, action: str) -> bool:
        return QMessageBox.question(
            self, "Confirm",
            f"Are you sure you want to {action}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes

    def _run_command(self, label: str, func, *args, **kwargs):
        api = self._get_api()
        self._worker = CommandWorker(api, label, func, *args, **kwargs)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._cmd_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _cmd_done(self, label):
        self._on_finished(f"{label}: done!")

    def _lock(self):
        api, vin = self._get_api(), self._get_vin()
        self._run_command("Lock", api.remote_lock, vin)

    def _unlock(self):
        if not self._confirm("unlock the car"):
            return
        api, vin = self._get_api(), self._get_vin()
        self._run_command("Unlock", api.remote_unlock, vin)

    def _climate_start(self):
        api, vin = self._get_api(), self._get_vin()
        self._run_command("Climate start", api.remote_climate_start, vin)

    def _climate_stop(self):
        api, vin = self._get_api(), self._get_vin()
        self._run_command("Climate stop", api.remote_climate_stop, vin)

    def _climate_settings(self):
        dlg = ClimateSettingsDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        api, vin = self._get_api(), self._get_vin()
        self._run_command(
            f"Climate ({dlg.temp}, {dlg.duration}min)",
            api.remote_climate_on, vin, temp=dlg.temp, duration=dlg.duration)

    def _charge_start(self):
        api, vin = self._get_api(), self._get_vin()
        self._run_command("Charge start", api.remote_charge_start, vin)

    def _charge_stop(self):
        api, vin = self._get_api(), self._get_vin()
        self._run_command("Charge stop", api.remote_charge_stop, vin)

    def _charge_limit(self):
        dlg = ChargeLimitDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        api, vin = self._get_api(), self._get_vin()
        self._run_command(
            f"Charge limit ({dlg.home_spin.value()}%/{dlg.away_spin.value()}%)",
            api.set_charge_limit, vin,
            home=dlg.home_spin.value(), away=dlg.away_spin.value())

    def _horn_lights(self):
        if not self._confirm("activate horn and lights"):
            return
        api, vin = self._get_api(), self._get_vin()
        self._run_command("Horn + Lights", api.remote_horn_lights, vin)

    def _locate(self):
        api, vin = self._get_api(), self._get_vin()
        self._run_command("Locate", api.request_car_location, vin)
