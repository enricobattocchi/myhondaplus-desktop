"""Main application window."""

import logging
import sys

from pymyhondaplus import HondaAPI
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .config import Settings
from .i18n import active_language, available_languages, load_language, t
from .icons import icon, pixmap
from .main_screen_controller import MainScreenController
from .session import AppSession
from .widgets.dashboard import DashboardWidget
from .widgets.login import LoginWidget
from .widgets.schedules import (
    ChargeLimitDialog,
    ChargeScheduleDialog,
    ClimateScheduleDialog,
    ClimateSettingsDialog,
)
from .widgets.status_bar import StatusBarWidget
from .widgets.trips import TripsWidget

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
        self._update_info = None  # (new_version, release_url) or None

        layout = QVBoxLayout(self)

        # Top bar
        top = QHBoxLayout()
        car_lbl = QLabel()
        car_lbl.setPixmap(icon("car").pixmap(20, 20))
        top.addWidget(car_lbl)
        self._vin_combo = QComboBox()
        self._vin_combo.setMinimumWidth(250)
        top.addWidget(self._vin_combo)
        top.addStretch()

        self._refresh_btn = QPushButton(icon("refresh-cw"), t("app.refresh"))
        top.addWidget(self._refresh_btn)

        self._refresh_car_btn = QPushButton(icon("car"), t("app.refresh_car"))
        top.addWidget(self._refresh_car_btn)

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
            "on_lock": lambda: self._controller.run_lock(),
            "on_unlock": lambda: self._controller.run_unlock(),
            "on_horn_lights": lambda: self._controller.run_horn_lights(),
            "on_charge_start": lambda: self._controller.run_charge_start(),
            "on_charge_stop": lambda: self._controller.run_charge_stop(),
            "on_charge_limit": lambda: self._controller.run_charge_limit(),
            "on_charge_schedule": lambda: self._controller.run_charge_schedule(),
            "on_climate_start": lambda: self._controller.run_climate_start(),
            "on_climate_stop": lambda: self._controller.run_climate_stop(),
            "on_climate_settings": lambda: self._controller.run_climate_settings(),
            "on_climate_schedule": lambda: self._controller.run_climate_schedule(),
            "on_locate": lambda: self._controller.run_locate(),
        })
        self._tabs.addTab(self._dashboard, icon("car"), t("app.dashboard"))

        # Trips tab
        self._trips = TripsWidget(
            get_api=lambda: self._api,
            get_vin=self.current_vin,
            get_vehicles=self.vehicles,
            on_status=self.show_status,
            on_error=self.show_error,
            on_auth_error=lambda: self._controller.handle_auth_error(),
        )
        self._tabs.addTab(self._trips, icon("route"), t("app.trips"))

        layout.addWidget(self._tabs)

        # Status bar
        self._status_bar = StatusBarWidget()
        layout.addWidget(self._status_bar)
        self._vehicles = []
        self._controller = MainScreenController(self, api, settings, on_logout)

        self._vin_combo.currentIndexChanged.connect(
            lambda _: self._controller.handle_vin_changed(self.current_vin())
        )
        self._refresh_btn.clicked.connect(
            lambda: self._controller.handle_refresh_current_tab(fresh=False)
        )
        self._refresh_car_btn.clicked.connect(
            lambda: self._controller.handle_refresh_current_tab(fresh=True)
        )
        self._tabs.currentChanged.connect(self._controller.handle_tab_changed)

    def activate(self):
        self._controller.activate()

    def set_api(self, api: HondaAPI):
        self._api = api
        self._controller.set_api(api)

    def vehicles(self) -> list[dict]:
        return self._vehicles

    def current_vin(self) -> str:
        idx = self._vin_combo.currentIndex()
        if idx >= 0 and idx < len(self._vehicles):
            return self._vehicles[idx]["vin"]
        return ""

    def current_tab_index(self) -> int:
        return self._tabs.currentIndex()

    def current_dashboard_status(self) -> dict:
        return self._dashboard.current_status()

    def populate_vehicles(self, vehicles: list[dict], saved_vin: str) -> str:
        self._vehicles = vehicles

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
        return self.current_vin()

    def update_dashboard_vin(self, vin: str):
        self._dashboard.set_vin(vin)

    def set_refresh_enabled(self, enabled: bool):
        self._refresh_btn.setEnabled(enabled)
        self._refresh_car_btn.setEnabled(enabled)

    def set_dashboard_actions_enabled(self, enabled: bool):
        self._dashboard.set_actions_enabled(enabled)

    def update_dashboard_status(self, status: dict):
        self._dashboard.update_status(status)

    def show_update_available(self, new_version: str, release_url: str):
        self._update_info = (new_version, release_url)
        self._update_label.setText(
            f'{t("app.update_available", version=new_version)} — '
            f'<a href="{release_url}" style="color: white;">'
            f'{t("app.download")}</a>')
        self._update_banner.setVisible(True)

    def show_status(self, text: str):
        self._status_bar.set_status(text)

    def show_success(self, text: str):
        self._status_bar.set_success(text)

    def show_error(self, text: str):
        self._status_bar.set_error(text)

    def load_trips(self):
        self._trips.load_trips()

    def open_charge_limit_dialog(self, status: dict, on_accept):
        dlg = ChargeLimitDialog(
            self,
            home=status.get("charge_limit_home", 80),
            away=status.get("charge_limit_away", 90),
        )
        dlg._buttons.accepted.disconnect()
        dlg._buttons.accepted.connect(lambda: on_accept(dlg))
        dlg.exec()

    def open_climate_settings_dialog(self, status: dict, on_accept):
        dlg = ClimateSettingsDialog(
            self,
            temp=status.get("climate_temp", "normal"),
            duration=status.get("climate_duration", 30),
            defrost=status.get("climate_defrost", True),
        )
        dlg._buttons.accepted.disconnect()
        dlg._buttons.accepted.connect(lambda: on_accept(dlg))
        dlg.exec()

    def open_climate_schedule_dialog(self, schedule: list, on_save, on_clear):
        dlg = ClimateScheduleDialog(self, schedule=schedule)
        dlg._on_save = lambda rules: on_save(dlg, rules)
        dlg._on_clear = lambda: on_clear(dlg)
        dlg.exec()

    def open_charge_schedule_dialog(self, schedule: list, on_save, on_clear):
        dlg = ChargeScheduleDialog(self, schedule=schedule)
        dlg._on_save = lambda rules: on_save(dlg, rules)
        dlg._on_clear = lambda: on_clear(dlg)
        dlg.exec()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(t("app.name"))
        self._session = AppSession()
        self._sync_session_refs()

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

        if self._session.restore_authenticated_session():
            self._show_main_screen()

    def _sync_session_refs(self):
        self._settings = self._session.settings
        self._storage = self._session.storage
        self._api = self._session.api

    def _show_main_screen(self):
        self._stack.setCurrentWidget(self._main)
        self._main.activate()

    def _on_login_success(self, tokens: dict, email: str, password: str):
        self._session.apply_login_tokens(tokens)
        self._sync_session_refs()
        self._show_main_screen()

    def _logout(self):
        self._session.reset()
        self._sync_session_refs()
        self._main.set_api(self._api)
        self._stack.setCurrentWidget(self._login)

    def showEvent(self, event):
        super().showEvent(event)
        # Lock to the natural size after layout is computed
        self.adjustSize()
        self.setFixedSize(self.size())

    def closeEvent(self, event):
        self._session.save_settings()
        super().closeEvent(event)


def _force_palette(app: QApplication, mode: str):
    """Force a light or dark palette regardless of system theme."""
    from PyQt6.QtGui import QColor, QPalette
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
