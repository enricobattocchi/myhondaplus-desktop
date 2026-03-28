"""Main application window."""

import sys
import logging

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QComboBox, QPushButton, QLabel, QFrame, QTabWidget,
    QDialog, QDialogButtonBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDesktopServices

from pymyhondaplus import HondaAPI, HondaAuth, get_storage
from pymyhondaplus.api import DEFAULT_TOKEN_FILE
from pymyhondaplus.auth import DEFAULT_DEVICE_KEY_FILE

from . import __version__
from .config import Settings
from .i18n import t, load_language, available_languages, active_language
from .icons import icon, pixmap
from .workers import DashboardWorker, VehiclesWorker, UpdateCheckWorker, CommandWorker, ScheduleLoadWorker, ScheduleSaveWorker
from .widgets.login import LoginWidget
from .widgets.dashboard import DashboardWidget
from .widgets.trips import TripsWidget
from .widgets.schedules import (
    ClimateScheduleDialog, ChargeScheduleDialog,
    ClimateSettingsDialog, ChargeLimitDialog,
)
from .widgets.status_bar import StatusBarWidget

logger = logging.getLogger(__name__)


REPO_URL = "https://github.com/enricobattocchi/myhondaplus-desktop"
LIB_URL = "https://github.com/enricobattocchi/pymyhondaplus"


class AboutDialog(QDialog):
    def __init__(self, parent=None, update_info: tuple = None,
                 settings: Settings = None):
        super().__init__(parent)
        self.setWindowTitle(t("app.about"))
        self.setFixedWidth(400)
        self._settings = settings
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(pixmap("app-icon", 96))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_lbl)

        title = QLabel(t("app.name"))
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        version = QLabel(t("app.version", version=__version__))
        version.setStyleSheet("color: gray;")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        if update_info:
            new_ver, release_url = update_info
            update_lbl = QLabel(
                f'<a href="{release_url}">'
                f'{t("app.version_available", version=new_ver)}</a>')
            update_lbl.setOpenExternalLinks(True)
            update_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            update_lbl.setStyleSheet("color: #3498db; font-weight: bold;")
            layout.addWidget(update_lbl)

        links = QLabel(
            f'<a href="{REPO_URL}">GitHub</a>'
            f' · Built with <a href="{LIB_URL}">pymyhondaplus</a>')
        links.setOpenExternalLinks(True)
        links.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(links)

        disclaimer = QLabel(t("app.disclaimer"))
        disclaimer.setStyleSheet("color: gray; font-size: 11px; margin-top: 10px;")
        disclaimer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        disclaimer.setWordWrap(True)
        layout.addWidget(disclaimer)

        # Language selector
        if self._settings is not None:
            lang_layout = QHBoxLayout()
            lang_layout.addStretch()
            lang_label = QLabel(t("app.language"))
            lang_layout.addWidget(lang_label)
            lang_combo = QComboBox()
            langs = available_languages()
            current_lang = active_language()
            for lang_code in langs:
                lang_combo.addItem(lang_code, lang_code)
            idx = lang_combo.findData(current_lang)
            if idx >= 0:
                lang_combo.setCurrentIndex(idx)
            lang_combo.currentIndexChanged.connect(
                lambda i: self._on_language_changed(lang_combo.currentData()))
            lang_layout.addWidget(lang_combo)
            lang_layout.addStretch()
            layout.addLayout(lang_layout)

            self._restart_label = QLabel(t("app.restart_language"))
            self._restart_label.setStyleSheet(
                "color: gray; font-size: 11px;")
            self._restart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._restart_label.setVisible(False)
            layout.addWidget(self._restart_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.accept)
        layout.addWidget(buttons)

    def _on_language_changed(self, lang_code: str):
        if self._settings is not None:
            self._settings.language = lang_code
            self._settings.save()
            self._restart_label.setVisible(True)


def _vehicle_label(v: dict) -> str:
    """Build a display label for a vehicle: 'Name (PLATE)' or just VIN."""
    name = v.get("name") or v["vin"]
    plate = v.get("plate")
    return f"{name} ({plate})" if plate else name


class MainScreen(QWidget):
    """Main screen with dashboard + commands."""

    def __init__(self, api: HondaAPI, settings: Settings, on_logout):
        super().__init__()
        self._api = api
        self._settings = settings
        self._vehicles = []  # list of {"vin", "name", "plate"}
        self._update_info = None  # (new_version, release_url) or None
        self._cached_climate_schedule = None  # cached after successful save
        self._cached_charge_schedule = None
        self._worker = None
        self._vehicles_worker = None

        layout = QVBoxLayout(self)

        # Top bar
        top = QHBoxLayout()
        car_lbl = QLabel()
        car_lbl.setPixmap(icon("car").pixmap(20, 20))
        top.addWidget(car_lbl)
        self._vin_combo = QComboBox()
        self._vin_combo.setMinimumWidth(250)
        self._vin_combo.currentIndexChanged.connect(self._on_vin_changed)
        top.addWidget(self._vin_combo)
        top.addStretch()

        refresh_btn = QPushButton(icon("refresh-cw"), t("app.refresh"))
        refresh_btn.clicked.connect(lambda: self._refresh_current_tab(fresh=False))
        top.addWidget(refresh_btn)

        refresh_car_btn = QPushButton(icon("car"), t("app.refresh_car"))
        refresh_car_btn.clicked.connect(lambda: self._refresh_current_tab(fresh=True))
        top.addWidget(refresh_car_btn)

        logout_btn = QPushButton(icon("log-out"), t("app.logout"))
        logout_btn.clicked.connect(on_logout)
        top.addWidget(logout_btn)

        about_btn = QPushButton(icon("info"), "")
        about_btn.setFixedWidth(32)
        about_btn.setToolTip(t("app.about"))
        about_btn.clicked.connect(
            lambda: AboutDialog(
                self, update_info=self._update_info,
                settings=self._settings).exec())
        top.addWidget(about_btn)

        layout.addLayout(top)

        # Update banner (hidden by default)
        self._update_banner = QFrame()
        self._update_banner.setStyleSheet(
            "QFrame { background: #1a5276; border-radius: 4px; padding: 4px; }")
        self._update_banner.setVisible(False)
        banner_layout = QHBoxLayout(self._update_banner)
        banner_layout.setContentsMargins(8, 4, 8, 4)
        self._update_label = QLabel()
        self._update_label.setOpenExternalLinks(True)
        self._update_label.setTextFormat(Qt.TextFormat.RichText)
        banner_layout.addWidget(self._update_label)
        banner_layout.addStretch()
        dismiss_btn = QPushButton(icon("x"), "")
        dismiss_btn.setFixedSize(24, 24)
        dismiss_btn.setFlat(True)
        dismiss_btn.clicked.connect(self._update_banner.hide)
        banner_layout.addWidget(dismiss_btn)
        layout.addWidget(self._update_banner)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line)

        # Tabs
        self._tabs = QTabWidget()

        # Dashboard tab
        self._dashboard = DashboardWidget(actions={
            "on_lock": self._cmd_lock,
            "on_unlock": self._cmd_unlock,
            "on_horn_lights": self._cmd_horn_lights,
            "on_charge_start": self._cmd_charge_start,
            "on_charge_stop": self._cmd_charge_stop,
            "on_charge_limit": self._cmd_charge_limit,
            "on_charge_schedule": self._cmd_charge_schedule,
            "on_climate_start": self._cmd_climate_start,
            "on_climate_stop": self._cmd_climate_stop,
            "on_climate_settings": self._cmd_climate_settings,
            "on_climate_schedule": self._cmd_climate_schedule,
            "on_locate": self._cmd_locate,
        })
        self._tabs.addTab(self._dashboard, icon("car"), t("app.dashboard"))

        # Trips tab
        self._trips = TripsWidget(
            get_api=lambda: self._api,
            get_vin=self._current_vin,
            get_vehicles=lambda: self._vehicles,
            on_status=self._status_bar_set_status,
            on_error=self._status_bar_set_error,
        )
        self._tabs.addTab(self._trips, icon("route"), t("app.trips"))
        self._tabs.currentChanged.connect(self._on_tab_changed)

        layout.addWidget(self._tabs)

        # Status bar
        self._status_bar = StatusBarWidget()
        layout.addWidget(self._status_bar)

    def activate(self):
        """Called when this screen becomes visible."""
        # First populate from cached vehicles in tokens (instant, no API call)
        if self._api.tokens.vehicles:
            self._populate_vehicles(self._api.tokens.vehicles)
        # Then refresh from API in background
        self._fetch_vehicles()
        # Check for updates
        self._check_update()

    def _current_vin(self) -> str:
        """Get the VIN for the currently selected vehicle."""
        idx = self._vin_combo.currentIndex()
        if idx >= 0 and idx < len(self._vehicles):
            return self._vehicles[idx]["vin"]
        return ""

    def _on_vin_changed(self, index: int):
        vin = self._current_vin()
        if vin:
            self._settings.vin = vin
            self._settings.save()
            self._cached_climate_schedule = None
            self._cached_charge_schedule = None
            self._dashboard.set_vin(vin)
            self._load_dashboard()

    def _populate_vehicles(self, vehicles: list[dict]):
        """Populate the combo box with vehicles."""
        self._vehicles = vehicles
        saved_vin = self._settings.vin

        self._vin_combo.blockSignals(True)
        self._vin_combo.clear()
        select_idx = 0
        for i, v in enumerate(vehicles):
            self._vin_combo.addItem(_vehicle_label(v))
            if v["vin"] == saved_vin:
                select_idx = i
        # Auto-select: saved VIN, or default_vin (single vehicle), or first
        if not saved_vin and len(vehicles) == 1:
            select_idx = 0
        self._vin_combo.setCurrentIndex(select_idx)
        self._vin_combo.blockSignals(False)

        if self._current_vin():
            self._dashboard.set_vin(self._current_vin())
            self._load_dashboard()

    def _fetch_vehicles(self):
        self._vehicles_worker = VehiclesWorker(self._api)
        self._vehicles_worker.finished.connect(self._on_vehicles)
        self._vehicles_worker.error.connect(
            lambda e: logger.warning("Failed to fetch vehicles: %s", e))
        self._vehicles_worker.start()

    def _on_vehicles(self, vehicles: list[dict]):
        self._populate_vehicles(vehicles)

    def _load_dashboard(self, fresh: bool = False):
        vin = self._current_vin()
        if not vin:
            self._status_bar.set_error(t("app.no_vin"))
            return

        self._worker = DashboardWorker(self._api, vin, fresh=fresh)
        self._worker.finished.connect(self._on_dashboard)
        self._worker.error.connect(self._status_bar.set_error)
        self._worker.progress.connect(self._status_bar.set_status)
        self._worker.start()

    def _on_dashboard(self, status: dict):
        self._dashboard.update_status(status)
        self._status_bar.set_success(t("app.status_loaded"))

    def _check_update(self):
        self._update_worker = UpdateCheckWorker(__version__)
        self._update_worker.update_available.connect(self._on_update_available)
        self._update_worker.start()

    def _on_update_available(self, new_version: str, release_url: str):
        self._update_info = (new_version, release_url)
        self._update_label.setText(
            f'{t("app.update_available", version=new_version)} — '
            f'<a href="{release_url}" style="color: white;">'
            f'{t("app.download")}</a>')
        self._update_banner.setVisible(True)

    def _refresh_current_tab(self, fresh: bool = False):
        index = self._tabs.currentIndex()
        if index == 0:
            self._load_dashboard(fresh=fresh)
        elif index == 1:
            self._trips.load_trips()

    def _on_tab_changed(self, index: int):
        if index == 1:  # Trips tab
            self._trips.load_trips()

    # -- Command helpers --

    def _run_command(self, label: str, func, *args, **kwargs):
        self._cmd_worker = CommandWorker(self._api, label, func, *args, **kwargs)
        self._cmd_worker.progress.connect(self._status_bar_set_status)
        self._cmd_worker.finished.connect(
            lambda lbl: (self._status_bar_set_success(t("commands.done", label=lbl)),
                         self._load_dashboard()))
        self._cmd_worker.error.connect(self._status_bar_set_error)
        self._cmd_worker.start()

    def _cmd_lock(self):
        self._run_command(t("commands.lock"), self._api.remote_lock, self._current_vin())

    def _cmd_unlock(self):
        self._run_command(t("commands.unlock"), self._api.remote_unlock, self._current_vin())

    def _cmd_horn_lights(self):
        self._run_command(t("commands.horn_lights"), self._api.remote_horn_lights, self._current_vin())

    def _cmd_charge_start(self):
        self._run_command(t("commands.charge_on"), self._api.remote_charge_start, self._current_vin())

    def _cmd_charge_stop(self):
        self._run_command(t("commands.charge_off"), self._api.remote_charge_stop, self._current_vin())

    def _cmd_charge_limit(self):
        status = self._dashboard._status
        dlg = ChargeLimitDialog(
            self,
            home=status.get("charge_limit_home", 80),
            away=status.get("charge_limit_away", 90),
        )

        def on_accept():
            dlg.set_saving(True, t("workers.sending", label=t("commands.charge_limit")))
            w = CommandWorker(
                self._api, t("commands.charge_limit"),
                self._api.set_charge_limit, self._current_vin(),
                home=dlg.home, away=dlg.away)
            w.progress.connect(lambda msg: dlg.set_saving(True, msg))
            w.finished.connect(lambda lbl: (
                dlg.set_saving(False),
                dlg.accept(),
                self._status_bar_set_success(t("commands.done", label=lbl)),
                self._load_dashboard()))
            w.error.connect(lambda msg: (
                dlg.set_saving(False, ""),
                self._status_bar_set_error(msg)))
            w.start()
            self._cmd_worker = w

        dlg._buttons.accepted.disconnect()
        dlg._buttons.accepted.connect(on_accept)
        dlg.exec()

    def _cmd_climate_start(self):
        self._run_command(t("commands.climate_on"), self._api.remote_climate_start, self._current_vin())

    def _cmd_climate_stop(self):
        self._run_command(t("commands.climate_off"), self._api.remote_climate_stop, self._current_vin())

    def _cmd_climate_settings(self):
        status = self._dashboard._status
        dlg = ClimateSettingsDialog(
            self,
            temp=status.get("climate_temp", "normal"),
            duration=status.get("climate_duration", 30),
            defrost=status.get("climate_defrost", True),
        )

        def on_accept():
            dlg.set_saving(True, t("workers.sending", label=t("commands.climate_settings")))
            w = CommandWorker(
                self._api, t("commands.climate_settings"),
                self._api.set_climate_settings, self._current_vin(),
                temp=dlg.temp, duration=dlg.duration, defrost=dlg.defrost)
            w.progress.connect(lambda msg: dlg.set_saving(True, msg))
            w.finished.connect(lambda lbl: (
                dlg.set_saving(False),
                dlg.accept(),
                self._status_bar_set_success(t("commands.done", label=lbl)),
                self._load_dashboard()))
            w.error.connect(lambda msg: (
                dlg.set_saving(False, ""),
                self._status_bar_set_error(msg)))
            w.start()
            self._cmd_worker = w

        dlg._buttons.accepted.disconnect()
        dlg._buttons.accepted.connect(on_accept)
        dlg.exec()

    def _cmd_locate(self):
        self._run_command(t("commands.locate"), self._api.request_car_location, self._current_vin())

    def _cmd_climate_schedule(self):
        vin = self._current_vin()
        if not vin:
            return
        if self._cached_climate_schedule is not None:
            self._show_climate_schedule_dialog(self._cached_climate_schedule)
        else:
            self._status_bar_set_status(t("schedules.loading"))
            self._sched_worker = ScheduleLoadWorker(self._api, vin)
            self._sched_worker.finished.connect(
                lambda data: self._show_climate_schedule_dialog(data["climate_schedule"]))
            self._sched_worker.error.connect(self._status_bar_set_error)
            self._sched_worker.start()

    def _show_climate_schedule_dialog(self, schedule: list):
        self._status_bar_set_success(t("schedules.loaded"))
        vin = self._current_vin()

        dlg = ClimateScheduleDialog(self, schedule=schedule)

        def on_save(rules):
            dlg.set_saving(True, t("workers.sending", label=t("schedules.climate")))
            def on_success(_):
                self._cached_climate_schedule = rules
                dlg.set_saving(False)
                self._status_bar_set_success(t("schedules.saved"))
            def on_error(msg):
                dlg.set_saving(False, "")
                self._status_bar_set_error(msg)
            w = ScheduleSaveWorker(self._api, t("schedules.climate"),
                                   self._api.set_climate_schedule, vin, rules)
            w.progress.connect(lambda msg: dlg.set_saving(True, msg))
            w.finished.connect(on_success)
            w.error.connect(on_error)
            w.start()
            self._sched_save_worker = w

        def on_clear():
            dlg.set_saving(True, t("workers.sending", label=t("schedules.climate")))
            def on_success(_):
                self._cached_climate_schedule = [{"enabled": False} for _ in range(7)]
                dlg.set_saving(False)
                self._status_bar_set_success(t("schedules.cleared"))
            def on_error(msg):
                dlg.set_saving(False, "")
                self._status_bar_set_error(msg)
            w = ScheduleSaveWorker(self._api, t("schedules.climate"),
                                   self._api.set_climate_schedule, vin, [])
            w.progress.connect(lambda msg: dlg.set_saving(True, msg))
            w.finished.connect(on_success)
            w.error.connect(on_error)
            w.start()
            self._sched_save_worker = w

        dlg._on_save = on_save
        dlg._on_clear = on_clear
        dlg.exec()

    def _cmd_charge_schedule(self):
        vin = self._current_vin()
        if not vin:
            return
        if self._cached_charge_schedule is not None:
            self._show_charge_schedule_dialog(self._cached_charge_schedule)
        else:
            self._status_bar_set_status(t("schedules.loading"))
            self._sched_worker = ScheduleLoadWorker(self._api, vin)
            self._sched_worker.finished.connect(
                lambda data: self._show_charge_schedule_dialog(data["charge_schedule"]))
            self._sched_worker.error.connect(self._status_bar_set_error)
            self._sched_worker.start()

    def _show_charge_schedule_dialog(self, schedule: list):
        self._status_bar_set_success(t("schedules.loaded"))
        vin = self._current_vin()

        dlg = ChargeScheduleDialog(self, schedule=schedule)

        def on_save(rules):
            dlg.set_saving(True, t("workers.sending", label=t("schedules.charge")))
            def on_success(_):
                self._cached_charge_schedule = rules
                dlg.set_saving(False)
                self._status_bar_set_success(t("schedules.saved"))
            def on_error(msg):
                dlg.set_saving(False, "")
                self._status_bar_set_error(msg)
            w = ScheduleSaveWorker(self._api, t("schedules.charge"),
                                   self._api.set_charge_schedule, vin, rules)
            w.progress.connect(lambda msg: dlg.set_saving(True, msg))
            w.finished.connect(on_success)
            w.error.connect(on_error)
            w.start()
            self._sched_save_worker = w

        def on_clear():
            dlg.set_saving(True, t("workers.sending", label=t("schedules.charge")))
            def on_success(_):
                self._cached_charge_schedule = [{"enabled": False} for _ in range(2)]
                dlg.set_saving(False)
                self._status_bar_set_success(t("schedules.cleared"))
            def on_error(msg):
                dlg.set_saving(False, "")
                self._status_bar_set_error(msg)
            w = ScheduleSaveWorker(self._api, t("schedules.charge"),
                                   self._api.set_charge_schedule, vin, [])
            w.progress.connect(lambda msg: dlg.set_saving(True, msg))
            w.finished.connect(on_success)
            w.error.connect(on_error)
            w.start()
            self._sched_save_worker = w

        dlg._on_save = on_save
        dlg._on_clear = on_clear
        dlg.exec()

    def _status_bar_set_status(self, text: str):
        self._status_bar.set_status(text)

    def _status_bar_set_success(self, text: str):
        self._status_bar.set_success(text)

    def _status_bar_set_error(self, text: str):
        self._status_bar.set_error(text)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(t("app.name"))
        self._settings = Settings.load()

        self._storage = get_storage(DEFAULT_TOKEN_FILE, DEFAULT_DEVICE_KEY_FILE)
        self._api = HondaAPI(storage=self._storage)

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Login screen
        self._login = LoginWidget(
            on_login_success=self._on_login_success,
            storage=self._storage)
        self._stack.addWidget(self._login)

        # Main screen
        self._main = MainScreen(
            self._api, self._settings, on_logout=self._logout)
        self._stack.addWidget(self._main)

        # Check if already logged in (try refresh if expired but has refresh token)
        if self._api.tokens.access_token:
            if self._api.tokens.is_expired and self._api.tokens.refresh_token:
                try:
                    self._api.refresh_auth()
                except Exception:
                    pass  # Will show login screen
            if not self._api.tokens.is_expired:
                self._stack.setCurrentWidget(self._main)
                self._main.activate()

    def _on_login_success(self, tokens: dict, email: str, password: str):
        user_id = HondaAuth.extract_user_id(tokens["access_token"])
        self._api.set_tokens(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_in=tokens.get("expires_in", 3599),
            user_id=user_id,
        )
        self._stack.setCurrentWidget(self._main)
        self._main.activate()  # will fetch vehicles and populate dropdown

    def _logout(self):
        self._storage.clear()
        self._api = HondaAPI(storage=self._storage)
        self._main._api = self._api
        self._stack.setCurrentWidget(self._login)

    def showEvent(self, event):
        super().showEvent(event)
        # Lock to the natural size after layout is computed
        self.adjustSize()
        self.setFixedSize(self.size())

    def closeEvent(self, event):
        self._settings.save()
        super().closeEvent(event)


def _force_palette(app: QApplication, mode: str):
    """Force a light or dark palette regardless of system theme."""
    from PyQt6.QtGui import QPalette, QColor
    app.setStyle("Fusion")
    p = QPalette()
    if mode == "light":
        p.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
        p.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
        p.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
        p.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
        p.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
        p.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
        p.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
        p.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
        p.setColor(QPalette.ColorRole.Link, QColor(0, 100, 200))
        p.setColor(QPalette.ColorRole.Highlight, QColor(50, 120, 200))
        p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        p.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 220))
        p.setColor(QPalette.ColorRole.ToolTipText, QColor(0, 0, 0))
        p.setColor(QPalette.ColorRole.PlaceholderText, QColor(128, 128, 128))
    else:  # dark
        p.setColor(QPalette.ColorRole.Window, QColor(45, 45, 45))
        p.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
        p.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
        p.setColor(QPalette.ColorRole.AlternateBase, QColor(50, 50, 50))
        p.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
        p.setColor(QPalette.ColorRole.Button, QColor(55, 55, 55))
        p.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220))
        p.setColor(QPalette.ColorRole.BrightText, QColor(255, 50, 50))
        p.setColor(QPalette.ColorRole.Link, QColor(80, 160, 255))
        p.setColor(QPalette.ColorRole.Highlight, QColor(50, 120, 200))
        p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        p.setColor(QPalette.ColorRole.ToolTipBase, QColor(50, 50, 50))
        p.setColor(QPalette.ColorRole.ToolTipText, QColor(220, 220, 220))
        p.setColor(QPalette.ColorRole.PlaceholderText, QColor(128, 128, 128))
    app.setPalette(p)


def main():
    import os
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    logging.basicConfig(level=logging.INFO)
    settings = Settings.load()
    load_language(settings.language)
    force_theme = None
    if "--light" in sys.argv:
        force_theme = "light"
    elif "--dark" in sys.argv:
        force_theme = "dark"
    if force_theme:
        os.environ.pop("QT_QPA_PLATFORMTHEME", None)
    app = QApplication(sys.argv)
    app.setApplicationName(t("app.name"))
    app.setWindowIcon(icon("app-icon"))
    if force_theme:
        _force_palette(app, force_theme)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
