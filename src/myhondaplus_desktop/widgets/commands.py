"""Command buttons panel."""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QMessageBox,
    QDialog, QFormLayout, QComboBox, QSpinBox, QDialogButtonBox,
)

from ..workers import CommandWorker
from ..icons import icon
from ..i18n import t
from pymyhondaplus import HondaAPI


class ClimateSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("commands.climate_settings"))
        layout = QFormLayout(self)

        self._temp_values = ["cooler", "normal", "hotter"]
        self.temp_combo = QComboBox()
        for val in self._temp_values:
            self.temp_combo.addItem(t(f"commands.{val}"), val)
        self.temp_combo.setCurrentIndex(1)  # normal
        layout.addRow(t("commands.temperature"), self.temp_combo)

        self.duration_combo = QComboBox()
        self.duration_combo.addItems(["10", "20", "30"])
        self.duration_combo.setCurrentText("30")
        layout.addRow(t("commands.duration"), self.duration_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    @property
    def temp(self) -> str:
        return self.temp_combo.currentData()

    @property
    def duration(self) -> int:
        return int(self.duration_combo.currentText())


class ChargeLimitDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("commands.charge_limit"))
        layout = QFormLayout(self)

        self.home_spin = QSpinBox()
        self.home_spin.setRange(50, 100)
        self.home_spin.setValue(80)
        self.home_spin.setSuffix("%")
        layout.addRow(t("commands.home"), self.home_spin)

        self.away_spin = QSpinBox()
        self.away_spin.setRange(50, 100)
        self.away_spin.setValue(90)
        self.away_spin.setSuffix("%")
        layout.addRow(t("commands.away"), self.away_spin)

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
            ("lock", t("commands.lock"), self._lock),
            ("lock-open", t("commands.unlock"), self._unlock),
            ("snowflake", t("commands.climate_on"), self._climate_start),
            ("circle-stop", t("commands.climate_off"), self._climate_stop),
            ("settings", t("commands.climate_settings"), self._climate_settings),
            ("zap", t("commands.charge_on"), self._charge_start),
            ("square", t("commands.charge_off"), self._charge_stop),
            ("battery-charging", t("commands.charge_limit"), self._charge_limit),
            ("megaphone", t("commands.horn_lights"), self._horn_lights),
            ("map-pin", t("commands.locate"), self._locate),
        ]

        for icon_name, label, handler in buttons:
            btn = QPushButton(icon(icon_name), label)
            btn.clicked.connect(handler)
            layout.addWidget(btn)

    def _confirm(self, action: str) -> bool:
        return QMessageBox.question(
            self, t("commands.confirm"),
            t("commands.confirm_action", action=action),
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
        self._on_finished(t("commands.done", label=label))

    def _lock(self):
        api, vin = self._get_api(), self._get_vin()
        self._run_command(t("commands.lock"), api.remote_lock, vin)

    def _unlock(self):
        if not self._confirm(t("commands.confirm_unlock")):
            return
        api, vin = self._get_api(), self._get_vin()
        self._run_command(t("commands.unlock"), api.remote_unlock, vin)

    def _climate_start(self):
        api, vin = self._get_api(), self._get_vin()
        self._run_command(t("commands.climate_on"), api.remote_climate_start, vin)

    def _climate_stop(self):
        api, vin = self._get_api(), self._get_vin()
        self._run_command(t("commands.climate_off"), api.remote_climate_stop, vin)

    def _climate_settings(self):
        dlg = ClimateSettingsDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        api, vin = self._get_api(), self._get_vin()
        self._run_command(
            f"{t('commands.climate_settings')} ({dlg.temp}, {dlg.duration}min)",
            api.remote_climate_on, vin, temp=dlg.temp, duration=dlg.duration)

    def _charge_start(self):
        api, vin = self._get_api(), self._get_vin()
        self._run_command(t("commands.charge_on"), api.remote_charge_start, vin)

    def _charge_stop(self):
        api, vin = self._get_api(), self._get_vin()
        self._run_command(t("commands.charge_off"), api.remote_charge_stop, vin)

    def _charge_limit(self):
        dlg = ChargeLimitDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        api, vin = self._get_api(), self._get_vin()
        self._run_command(
            f"{t('commands.charge_limit')} ({dlg.home_spin.value()}%/{dlg.away_spin.value()}%)",
            api.set_charge_limit, vin,
            home=dlg.home_spin.value(), away=dlg.away_spin.value())

    def _horn_lights(self):
        if not self._confirm(t("commands.confirm_horn")):
            return
        api, vin = self._get_api(), self._get_vin()
        self._run_command(t("commands.horn_lights"), api.remote_horn_lights, vin)

    def _locate(self):
        api, vin = self._get_api(), self._get_vin()
        self._run_command(t("commands.locate"), api.request_car_location, vin)
