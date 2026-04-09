"""Orchestration for the main screen UI."""

import logging

from . import __version__
from .i18n import t
from .widgets.schedules import ChargeLimitDialog, ClimateSettingsDialog
from .workers import (
    CommandWorker,
    DashboardWorker,
    ScheduleLoadWorker,
    ScheduleSaveWorker,
    UpdateCheckWorker,
    VehiclesWorker,
)

logger = logging.getLogger(__name__)


class MainScreenController:
    """Coordinates MainScreen state, workers, and view updates."""

    def __init__(self, view, api, settings, on_logout):
        self._view = view
        self._api = api
        self._settings = settings
        self._on_logout = on_logout
        self._vehicles = []
        self._cached_climate_schedule = None
        self._cached_charge_schedule = None
        self._dashboard_worker = None
        self._vehicles_worker = None
        self._command_worker = None
        self._update_worker = None
        self._schedule_worker = None
        self._schedule_save_worker = None

    def set_api(self, api):
        self._api = api

    def activate(self):
        if self._api.tokens.vehicles:
            self._apply_vehicles(self._api.tokens.vehicles)
        self._fetch_vehicles()
        self._check_update()

    def handle_vin_changed(self, vin: str):
        if not vin:
            return
        self._settings.vin = vin
        self._settings.save()
        self._reset_schedule_cache()
        self._view.update_dashboard_vin(vin)
        self._load_dashboard()

    def handle_refresh_current_tab(self, fresh: bool = False):
        self._reset_schedule_cache()
        index = self._view.current_tab_index()
        if index == 0:
            self._load_dashboard(fresh=fresh)
        elif index == 1:
            self._view.load_trips()

    def handle_tab_changed(self, index: int):
        if index == 1:
            self._view.load_trips()

    def handle_auth_error(self):
        self._view.show_error(t("app.session_expired"))
        self._on_logout()

    def run_lock(self):
        self._run_command(t("commands.lock"), self._api.remote_lock, self._view.current_vin())

    def run_unlock(self):
        self._run_command(t("commands.unlock"), self._api.remote_unlock, self._view.current_vin())

    def run_horn_lights(self):
        self._run_command(
            t("commands.horn_lights"), self._api.remote_horn_lights, self._view.current_vin()
        )

    def run_charge_start(self):
        self._run_command(
            t("commands.charge_on"), self._api.remote_charge_start, self._view.current_vin()
        )

    def run_charge_stop(self):
        self._run_command(
            t("commands.charge_off"), self._api.remote_charge_stop, self._view.current_vin()
        )

    def run_charge_limit(self):
        status = self._view.current_dashboard_status()

        def on_accept(dialog: ChargeLimitDialog):
            self._run_dialog_command(
                dialog,
                t("commands.charge_limit"),
                self._api.set_charge_limit,
                self._view.current_vin(),
                home=dialog.home,
                away=dialog.away,
            )

        self._view.open_charge_limit_dialog(status, on_accept)

    def run_climate_start(self):
        self._run_command(
            t("commands.climate_on"), self._api.remote_climate_start, self._view.current_vin()
        )

    def run_climate_stop(self):
        self._run_command(
            t("commands.climate_off"), self._api.remote_climate_stop, self._view.current_vin()
        )

    def run_climate_settings(self):
        status = self._view.current_dashboard_status()

        def on_accept(dialog: ClimateSettingsDialog):
            self._run_dialog_command(
                dialog,
                t("commands.climate_settings"),
                self._api.set_climate_settings,
                self._view.current_vin(),
                temp=dialog.temp,
                duration=dialog.duration,
                defrost=dialog.defrost,
            )

        self._view.open_climate_settings_dialog(status, on_accept)

    def run_locate(self):
        self._run_command(
            t("commands.locate"), self._api.request_car_location, self._view.current_vin()
        )

    def run_climate_schedule(self):
        vin = self._view.current_vin()
        if not vin:
            return
        if self._cached_climate_schedule is not None:
            self._show_climate_schedule_dialog(self._cached_climate_schedule)
            return
        self._view.show_status(t("schedules.loading"))
        self._schedule_worker = ScheduleLoadWorker(self._api, vin)
        self._schedule_worker.auth_error.connect(self.handle_auth_error)
        self._schedule_worker.finished.connect(
            lambda data: self._show_climate_schedule_dialog(data["climate_schedule"])
        )
        self._schedule_worker.error.connect(self._view.show_error)
        self._schedule_worker.start()

    def run_charge_schedule(self):
        vin = self._view.current_vin()
        if not vin:
            return
        if self._cached_charge_schedule is not None:
            self._show_charge_schedule_dialog(self._cached_charge_schedule)
            return
        self._view.show_status(t("schedules.loading"))
        self._schedule_worker = ScheduleLoadWorker(self._api, vin)
        self._schedule_worker.auth_error.connect(self.handle_auth_error)
        self._schedule_worker.finished.connect(
            lambda data: self._show_charge_schedule_dialog(data["charge_schedule"])
        )
        self._schedule_worker.error.connect(self._view.show_error)
        self._schedule_worker.start()

    def _apply_vehicles(self, vehicles: list[dict]):
        self._vehicles = vehicles
        vin = self._view.populate_vehicles(vehicles, self._settings.vin)
        if vin:
            self._view.update_dashboard_vin(vin)
            self._load_dashboard()

    def _reset_schedule_cache(self):
        self._cached_climate_schedule = None
        self._cached_charge_schedule = None

    def _fetch_vehicles(self):
        self._vehicles_worker = VehiclesWorker(self._api)
        self._vehicles_worker.finished.connect(self._apply_vehicles)
        self._vehicles_worker.error.connect(self._on_vehicle_fetch_error)
        self._vehicles_worker.start()

    def _on_vehicle_fetch_error(self, error: str):
        logger.warning("Failed to fetch vehicles: %s", error)

    def _load_dashboard(self, fresh: bool = False):
        vin = self._view.current_vin()
        if not vin:
            self._view.show_error(t("app.no_vin"))
            return
        self._view.set_refresh_enabled(False)
        self._dashboard_worker = DashboardWorker(self._api, vin, fresh=fresh)
        self._dashboard_worker.finished.connect(self._on_dashboard_loaded)
        self._dashboard_worker.auth_error.connect(self.handle_auth_error)
        self._dashboard_worker.error.connect(self._on_dashboard_error)
        self._dashboard_worker.progress.connect(self._view.show_status)
        self._dashboard_worker.start()

    def _on_dashboard_loaded(self, status: dict):
        self._view.set_refresh_enabled(True)
        self._view.update_dashboard_status(status)
        self._view.set_dashboard_actions_enabled(True)
        if status.pop("_refresh_stale", False):
            self._view.show_warning(t("app.refresh_stale"))
        else:
            self._view.show_success(t("app.status_loaded"))

    def _on_dashboard_error(self, message: str):
        self._view.set_refresh_enabled(True)
        self._view.show_error(message)

    def _check_update(self):
        self._update_worker = UpdateCheckWorker(__version__)
        self._update_worker.update_available.connect(self._view.show_update_available)
        self._update_worker.start()

    def _run_command(self, label: str, func, *args, **kwargs):
        self._view.set_dashboard_actions_enabled(False)
        self._command_worker = CommandWorker(self._api, label, func, *args, **kwargs)
        self._command_worker.auth_error.connect(self.handle_auth_error)
        self._command_worker.progress.connect(self._view.show_status)
        self._command_worker.finished.connect(self._on_command_success)
        self._command_worker.error.connect(self._on_command_error)
        self._command_worker.start()

    def _run_dialog_command(self, dialog, label: str, func, *args, **kwargs):
        dialog.set_saving(True, t("workers.sending", label=label))
        self._command_worker = CommandWorker(self._api, label, func, *args, **kwargs)
        self._command_worker.auth_error.connect(self.handle_auth_error)
        self._command_worker.progress.connect(lambda message: dialog.set_saving(True, message))
        self._command_worker.finished.connect(
            lambda worker_label: self._on_dialog_command_success(dialog, worker_label)
        )
        self._command_worker.error.connect(lambda message: self._on_dialog_command_error(dialog, message))
        self._command_worker.start()

    def _on_command_success(self, label: str):
        self._view.set_dashboard_actions_enabled(True)
        self._view.show_success(t("commands.done", label=label))
        self._load_dashboard()

    def _on_command_error(self, message: str):
        self._view.set_dashboard_actions_enabled(True)
        self._view.show_error(message)

    def _on_dialog_command_success(self, dialog, label: str):
        dialog.set_saving(False)
        dialog.accept()
        self._view.show_success(t("commands.done", label=label))
        self._load_dashboard()

    def _on_dialog_command_error(self, dialog, message: str):
        dialog.set_saving(False, "")
        self._view.show_error(message)

    def _show_climate_schedule_dialog(self, schedule: list):
        self._view.show_success(t("schedules.loaded"))
        self._view.open_climate_schedule_dialog(
            schedule,
            self._save_climate_schedule,
            self._clear_climate_schedule,
        )

    def _show_charge_schedule_dialog(self, schedule: list):
        self._view.show_success(t("schedules.loaded"))
        self._view.open_charge_schedule_dialog(
            schedule,
            self._save_charge_schedule,
            self._clear_charge_schedule,
        )

    def _save_climate_schedule(self, dialog, rules: list):
        self._run_schedule_save(
            dialog,
            t("schedules.climate"),
            self._api.set_climate_schedule,
            rules,
            lambda: self._cache_climate_schedule(rules),
            t("schedules.saved"),
        )

    def _clear_climate_schedule(self, dialog):
        cleared = [{"enabled": False} for _ in range(7)]
        self._run_schedule_save(
            dialog,
            t("schedules.climate"),
            self._api.set_climate_schedule,
            [],
            lambda: self._cache_climate_schedule(cleared),
            t("schedules.cleared"),
        )

    def _save_charge_schedule(self, dialog, rules: list):
        self._run_schedule_save(
            dialog,
            t("schedules.charge"),
            self._api.set_charge_schedule,
            rules,
            lambda: self._cache_charge_schedule(rules),
            t("schedules.saved"),
        )

    def _clear_charge_schedule(self, dialog):
        cleared = [{"enabled": False} for _ in range(2)]
        self._run_schedule_save(
            dialog,
            t("schedules.charge"),
            self._api.set_charge_schedule,
            [],
            lambda: self._cache_charge_schedule(cleared),
            t("schedules.cleared"),
        )

    def _run_schedule_save(self, dialog, label: str, func, payload, on_success, success_message: str):
        vin = self._view.current_vin()
        dialog.set_saving(True, t("workers.sending", label=label))
        self._schedule_save_worker = ScheduleSaveWorker(self._api, label, func, vin, payload)
        self._schedule_save_worker.auth_error.connect(self.handle_auth_error)
        self._schedule_save_worker.progress.connect(lambda message: dialog.set_saving(True, message))
        self._schedule_save_worker.finished.connect(
            lambda _: self._on_schedule_save_success(dialog, on_success, success_message)
        )
        self._schedule_save_worker.error.connect(
            lambda message: self._on_schedule_save_error(dialog, message)
        )
        self._schedule_save_worker.start()

    def _on_schedule_save_success(self, dialog, on_success, success_message: str):
        on_success()
        dialog.set_saving(False)
        self._view.show_success(success_message)

    def _on_schedule_save_error(self, dialog, message: str):
        dialog.set_saving(False, "")
        self._view.show_error(message)

    def _cache_climate_schedule(self, rules: list):
        self._cached_climate_schedule = rules

    def _cache_charge_schedule(self, rules: list):
        self._cached_charge_schedule = rules
