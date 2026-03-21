"""Main application window."""

import sys
import logging

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QComboBox, QPushButton, QLabel, QFrame,
)
from PyQt6.QtCore import Qt

from pymyhondaplus import HondaAPI, HondaAuth
from pymyhondaplus.api import DEFAULT_TOKEN_FILE

from .config import Settings
from .workers import DashboardWorker, VehiclesWorker
from .widgets.login import LoginWidget
from .widgets.dashboard import DashboardWidget
from .widgets.commands import CommandsWidget
from .widgets.status_bar import StatusBarWidget

logger = logging.getLogger(__name__)


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
        self._worker = None
        self._vehicles_worker = None

        layout = QVBoxLayout(self)

        # Top bar
        top = QHBoxLayout()
        top.addWidget(QLabel("\U0001F697"))
        self._vin_combo = QComboBox()
        self._vin_combo.setMinimumWidth(250)
        self._vin_combo.currentIndexChanged.connect(self._on_vin_changed)
        top.addWidget(self._vin_combo)
        top.addStretch()

        refresh_btn = QPushButton("\U0001F504 Refresh")
        refresh_btn.clicked.connect(lambda: self._load_dashboard(fresh=False))
        top.addWidget(refresh_btn)

        refresh_car_btn = QPushButton("\U0001F697 Refresh from Car")
        refresh_car_btn.clicked.connect(lambda: self._load_dashboard(fresh=True))
        top.addWidget(refresh_car_btn)

        logout_btn = QPushButton("\U0001F6AA Logout")
        logout_btn.clicked.connect(on_logout)
        top.addWidget(logout_btn)

        layout.addLayout(top)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line)

        # Dashboard
        self._dashboard = DashboardWidget()
        layout.addWidget(self._dashboard)

        # Separator
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line2)

        # Commands
        self._commands = CommandsWidget(
            get_api=lambda: self._api,
            get_vin=self._current_vin,
            on_progress=self._status_bar_set_status,
            on_finished=self._status_bar_set_success,
            on_error=self._status_bar_set_error,
        )
        layout.addWidget(self._commands)

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
            self._status_bar.set_error("No VIN selected")
            return

        self._worker = DashboardWorker(self._api, vin, fresh=fresh)
        self._worker.finished.connect(self._on_dashboard)
        self._worker.error.connect(self._status_bar.set_error)
        self._worker.progress.connect(self._status_bar.set_status)
        self._worker.start()

    def _on_dashboard(self, status: dict):
        self._dashboard.update_status(status)
        self._status_bar.set_success("Status loaded")

    def _status_bar_set_status(self, text: str):
        self._status_bar.set_status(text)

    def _status_bar_set_success(self, text: str):
        self._status_bar.set_success(text)

    def _status_bar_set_error(self, text: str):
        self._status_bar.set_error(text)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My Honda+")
        self._settings = Settings.load()
        self.resize(self._settings.window_width, self._settings.window_height)

        self._api = HondaAPI(token_file=DEFAULT_TOKEN_FILE)

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Login screen
        self._login = LoginWidget(on_login_success=self._on_login_success)
        self._stack.addWidget(self._login)

        # Main screen
        self._main = MainScreen(
            self._api, self._settings, on_logout=self._logout)
        self._stack.addWidget(self._main)

        # Check if already logged in
        if self._api.tokens.access_token and not self._api.tokens.is_expired:
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
        import os
        for path in [DEFAULT_TOKEN_FILE]:
            if path.exists():
                os.unlink(path)
        self._api = HondaAPI(token_file=DEFAULT_TOKEN_FILE)
        self._main._api = self._api
        self._stack.setCurrentWidget(self._login)

    def closeEvent(self, event):
        self._settings.window_width = self.width()
        self._settings.window_height = self.height()
        self._settings.save()
        super().closeEvent(event)


def main():
    logging.basicConfig(level=logging.INFO)
    app = QApplication(sys.argv)
    app.setApplicationName("My Honda+")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
