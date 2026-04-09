"""Tests for the main screen controller."""

import pytest

from myhondaplus_desktop.config import Settings
from myhondaplus_desktop.main_screen_controller import MainScreenController


@pytest.fixture(autouse=True)
def stub_translations(monkeypatch):
    def fake_t(key, **kwargs):
        if key == "commands.done":
            return f"{kwargs['label']}: done!"
        return key

    monkeypatch.setattr("myhondaplus_desktop.main_screen_controller.t", fake_t)


class FakeSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args):
        for callback in list(self._callbacks):
            callback(*args)


class FakeWorker:
    def __init__(self):
        self.finished = FakeSignal()
        self.error = FakeSignal()
        self.progress = FakeSignal()
        self.auth_error = FakeSignal()
        self.update_available = FakeSignal()
        self.started = False

    def start(self):
        self.started = True


class FakeTokens:
    def __init__(self):
        self.vehicles = []


class FakeAPI:
    def __init__(self):
        self.tokens = FakeTokens()
        self.remote_lock = object()
        self.remote_unlock = object()
        self.remote_horn_lights = object()
        self.remote_charge_start = object()
        self.remote_charge_stop = object()
        self.set_charge_limit = object()
        self.remote_climate_start = object()
        self.remote_climate_stop = object()
        self.set_climate_settings = object()
        self.request_car_location = object()
        self.set_climate_schedule = object()
        self.set_charge_schedule = object()


class FakeView:
    def __init__(self):
        self._current_vin = ""
        self._current_tab_index = 0
        self._dashboard_status = {}
        self.populate_calls = []
        self.dashboard_vins = []
        self.refresh_enabled = []
        self.dashboard_actions = []
        self.dashboard_updates = []
        self.status_messages = []
        self.success_messages = []
        self.warning_messages = []
        self.error_messages = []
        self.update_banners = []
        self.load_trips_calls = 0

    def current_vin(self):
        return self._current_vin

    def current_tab_index(self):
        return self._current_tab_index

    def current_dashboard_status(self):
        return self._dashboard_status

    def populate_vehicles(self, vehicles, saved_vin):
        self.populate_calls.append((vehicles, saved_vin))
        if saved_vin and any(v["vin"] == saved_vin for v in vehicles):
            self._current_vin = saved_vin
        elif vehicles:
            self._current_vin = vehicles[0]["vin"]
        else:
            self._current_vin = ""
        return self._current_vin

    def update_dashboard_vin(self, vin):
        self._current_vin = vin
        self.dashboard_vins.append(vin)

    def set_refresh_enabled(self, enabled):
        self.refresh_enabled.append(enabled)

    def set_dashboard_actions_enabled(self, enabled):
        self.dashboard_actions.append(enabled)

    def update_dashboard_status(self, status):
        self.dashboard_updates.append(status)

    def show_status(self, text):
        self.status_messages.append(text)

    def show_success(self, text):
        self.success_messages.append(text)

    def show_warning(self, text):
        self.warning_messages.append(text)

    def show_error(self, text):
        self.error_messages.append(text)

    def show_update_available(self, version, url):
        self.update_banners.append((version, url))

    def load_trips(self):
        self.load_trips_calls += 1

    def open_charge_limit_dialog(self, status, on_accept):
        self.charge_limit_dialog = (status, on_accept)

    def open_climate_settings_dialog(self, status, on_accept):
        self.climate_settings_dialog = (status, on_accept)

    def open_climate_schedule_dialog(self, schedule, on_save, on_clear):
        self.climate_schedule_dialog = (schedule, on_save, on_clear)

    def open_charge_schedule_dialog(self, schedule, on_save, on_clear):
        self.charge_schedule_dialog = (schedule, on_save, on_clear)


class FakeSettings(Settings):
    def __init__(self, vin="", language=""):
        super().__init__(vin=vin, language=language)
        self.save_calls = 0

    def save(self):
        self.save_calls += 1


def test_activate_populates_cached_vehicles_and_starts_refresh(monkeypatch):
    vehicles_worker = FakeWorker()
    update_worker = FakeWorker()
    dashboard_worker = FakeWorker()
    api = FakeAPI()
    api.tokens.vehicles = [{"vin": "VIN123", "name": "Honda e"}]
    view = FakeView()
    settings = FakeSettings(vin="VIN123")

    monkeypatch.setattr(
        "myhondaplus_desktop.main_screen_controller.VehiclesWorker", lambda api: vehicles_worker
    )
    monkeypatch.setattr(
        "myhondaplus_desktop.main_screen_controller.UpdateCheckWorker",
        lambda current_version: update_worker,
    )
    monkeypatch.setattr(
        "myhondaplus_desktop.main_screen_controller.DashboardWorker",
        lambda api, vin, fresh=False: dashboard_worker,
    )

    controller = MainScreenController(view, api, settings, lambda: None)
    controller.activate()

    assert view.populate_calls == [([{"vin": "VIN123", "name": "Honda e"}], "VIN123")]
    assert view.dashboard_vins == ["VIN123"]
    assert view.refresh_enabled == [False]
    assert vehicles_worker.started is True
    assert update_worker.started is True
    assert dashboard_worker.started is True


def test_handle_vin_changed_persists_and_reloads_dashboard(monkeypatch):
    dashboard_worker = FakeWorker()
    api = FakeAPI()
    view = FakeView()
    settings = FakeSettings()

    monkeypatch.setattr(
        "myhondaplus_desktop.main_screen_controller.DashboardWorker",
        lambda api, vin, fresh=False: dashboard_worker,
    )

    controller = MainScreenController(view, api, settings, lambda: None)
    controller.handle_vin_changed("VIN123")

    assert settings.vin == "VIN123"
    assert settings.save_calls == 1
    assert view.dashboard_vins == ["VIN123"]
    assert dashboard_worker.started is True


def test_command_success_reloads_dashboard(monkeypatch):
    command_worker = FakeWorker()
    dashboard_worker = FakeWorker()
    api = FakeAPI()
    view = FakeView()
    view._current_vin = "VIN123"
    settings = FakeSettings(vin="VIN123")

    monkeypatch.setattr(
        "myhondaplus_desktop.main_screen_controller.CommandWorker",
        lambda *args, **kwargs: command_worker,
    )
    monkeypatch.setattr(
        "myhondaplus_desktop.main_screen_controller.DashboardWorker",
        lambda api, vin, fresh=False: dashboard_worker,
    )

    controller = MainScreenController(view, api, settings, lambda: None)
    controller.run_lock()
    command_worker.finished.emit("Lock")

    assert view.dashboard_actions == [False, True]
    assert view.success_messages[-1] == "Lock: done!"
    assert view.refresh_enabled == [False]
    assert dashboard_worker.started is True


def test_update_available_is_forwarded_to_view(monkeypatch):
    update_worker = FakeWorker()
    vehicles_worker = FakeWorker()
    api = FakeAPI()
    view = FakeView()
    settings = FakeSettings()

    monkeypatch.setattr(
        "myhondaplus_desktop.main_screen_controller.UpdateCheckWorker",
        lambda current_version: update_worker,
    )
    monkeypatch.setattr(
        "myhondaplus_desktop.main_screen_controller.VehiclesWorker", lambda api: vehicles_worker
    )

    controller = MainScreenController(view, api, settings, lambda: None)
    controller.activate()
    update_worker.update_available.emit("2.2.0", "https://example.com/release")

    assert view.update_banners == [("2.2.0", "https://example.com/release")]


def test_auth_error_triggers_logout_from_dashboard_worker(monkeypatch):
    dashboard_worker = FakeWorker()
    api = FakeAPI()
    view = FakeView()
    view._current_vin = "VIN123"
    settings = FakeSettings(vin="VIN123")
    state = {"logout_calls": 0}

    monkeypatch.setattr(
        "myhondaplus_desktop.main_screen_controller.DashboardWorker",
        lambda api, vin, fresh=False: dashboard_worker,
    )

    controller = MainScreenController(view, api, settings, lambda: state.update(logout_calls=state["logout_calls"] + 1))
    controller.handle_refresh_current_tab()
    dashboard_worker.auth_error.emit()

    assert state["logout_calls"] == 1
    assert view.error_messages[-1] == "app.session_expired"


def test_auth_error_triggers_logout_from_command_worker(monkeypatch):
    command_worker = FakeWorker()
    api = FakeAPI()
    view = FakeView()
    view._current_vin = "VIN123"
    settings = FakeSettings(vin="VIN123")
    state = {"logout_calls": 0}

    monkeypatch.setattr(
        "myhondaplus_desktop.main_screen_controller.CommandWorker",
        lambda *args, **kwargs: command_worker,
    )

    controller = MainScreenController(view, api, settings, lambda: state.update(logout_calls=state["logout_calls"] + 1))
    controller.run_lock()
    command_worker.auth_error.emit()

    assert state["logout_calls"] == 1
    assert view.error_messages[-1] == "app.session_expired"


def test_auth_error_triggers_logout_from_schedule_worker(monkeypatch):
    schedule_worker = FakeWorker()
    api = FakeAPI()
    view = FakeView()
    view._current_vin = "VIN123"
    settings = FakeSettings(vin="VIN123")
    state = {"logout_calls": 0}

    monkeypatch.setattr(
        "myhondaplus_desktop.main_screen_controller.ScheduleLoadWorker",
        lambda api, vin: schedule_worker,
    )

    controller = MainScreenController(view, api, settings, lambda: state.update(logout_calls=state["logout_calls"] + 1))
    controller.run_climate_schedule()
    schedule_worker.auth_error.emit()

    assert state["logout_calls"] == 1
    assert view.error_messages[-1] == "app.session_expired"


def test_dashboard_loaded_shows_warning_when_refresh_stale(monkeypatch):
    dashboard_worker = FakeWorker()
    api = FakeAPI()
    view = FakeView()
    view._current_vin = "VIN123"
    settings = FakeSettings(vin="VIN123")

    monkeypatch.setattr(
        "myhondaplus_desktop.main_screen_controller.DashboardWorker",
        lambda api, vin, fresh=False: dashboard_worker,
    )

    controller = MainScreenController(view, api, settings, lambda: None)
    controller.handle_refresh_current_tab(fresh=True)
    dashboard_worker.finished.emit({"battery": 70, "_refresh_stale": True})

    assert view.warning_messages == ["app.refresh_stale"]
    assert view.success_messages == []


def test_dashboard_loaded_shows_success_when_refresh_ok(monkeypatch):
    dashboard_worker = FakeWorker()
    api = FakeAPI()
    view = FakeView()
    view._current_vin = "VIN123"
    settings = FakeSettings(vin="VIN123")

    monkeypatch.setattr(
        "myhondaplus_desktop.main_screen_controller.DashboardWorker",
        lambda api, vin, fresh=False: dashboard_worker,
    )

    controller = MainScreenController(view, api, settings, lambda: None)
    controller.handle_refresh_current_tab()
    dashboard_worker.finished.emit({"battery": 90})

    assert view.success_messages == ["app.status_loaded"]
    assert view.warning_messages == []
