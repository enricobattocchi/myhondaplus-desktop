"""Tests for app helpers."""

import builtins
import sys
from types import ModuleType

from myhondaplus_desktop.__main__ import _load_main
from myhondaplus_desktop.app import MainScreen, _vehicle_label


def test_vehicle_label_with_plate():
    v = {"vin": "JHMZC78", "name": "Honda e", "plate": "GE395KM"}
    assert _vehicle_label(v) == "Honda e (GE395KM)"


def test_vehicle_label_without_plate():
    v = {"vin": "JHMZC78", "name": "Honda e", "plate": ""}
    assert _vehicle_label(v) == "Honda e"


def test_vehicle_label_no_name():
    v = {"vin": "JHMZC78", "name": "", "plate": "GE395KM"}
    assert _vehicle_label(v) == "JHMZC78 (GE395KM)"


def test_vehicle_label_no_name_no_plate():
    v = {"vin": "JHMZC78", "name": "", "plate": ""}
    assert _vehicle_label(v) == "JHMZC78"


def test_open_charge_limit_dialog_uses_explicit_accept_handler(monkeypatch):
    state = {}

    class FakeDialog:
        def __init__(self, parent, home, away):
            state["dialog"] = self
            state["parent"] = parent
            state["home"] = home
            state["away"] = away

        def set_accept_handler(self, handler):
            state["handler"] = handler

        def exec(self):
            state["exec_called"] = True

    monkeypatch.setattr("myhondaplus_desktop.app.ChargeLimitDialog", FakeDialog)

    accepted = {}

    def on_accept(dialog):
        accepted["dialog"] = dialog

    screen = object()
    MainScreen.open_charge_limit_dialog(
        screen,
        {"charge_limit_home": 85, "charge_limit_away": 95},
        on_accept,
    )

    assert state["parent"] is screen
    assert state["home"] == 85
    assert state["away"] == 95
    assert state["exec_called"] is True
    state["handler"]()
    assert accepted["dialog"] is state["dialog"]


def test_open_climate_settings_dialog_uses_explicit_accept_handler(monkeypatch):
    state = {}

    class FakeDialog:
        def __init__(self, parent, temp, duration, defrost):
            state["dialog"] = self
            state["parent"] = parent
            state["temp"] = temp
            state["duration"] = duration
            state["defrost"] = defrost

        def set_accept_handler(self, handler):
            state["handler"] = handler

        def exec(self):
            state["exec_called"] = True

    monkeypatch.setattr("myhondaplus_desktop.app.ClimateSettingsDialog", FakeDialog)

    accepted = {}

    def on_accept(dialog):
        accepted["dialog"] = dialog

    screen = object()
    MainScreen.open_climate_settings_dialog(
        screen,
        {
            "climate_temp": "cooler",
            "climate_duration": 20,
            "climate_defrost": False,
        },
        on_accept,
    )

    assert state["parent"] is screen
    assert state["temp"] == "cooler"
    assert state["duration"] == 20
    assert state["defrost"] is False
    assert state["exec_called"] is True
    state["handler"]()
    assert accepted["dialog"] is state["dialog"]


def test_open_climate_schedule_dialog_passes_callbacks_via_constructor(monkeypatch):
    state = {}

    class FakeDialog:
        def __init__(self, parent, schedule, on_save, on_clear):
            state["dialog"] = self
            state["parent"] = parent
            state["schedule"] = schedule
            state["on_save"] = on_save
            state["on_clear"] = on_clear

        def exec(self):
            state["exec_called"] = True

    monkeypatch.setattr("myhondaplus_desktop.app.ClimateScheduleDialog", FakeDialog)

    saved = {}
    cleared = {}

    def on_save(dialog, rules):
        saved["dialog"] = dialog
        saved["rules"] = rules

    def on_clear(dialog):
        cleared["dialog"] = dialog

    screen = object()
    schedule = [{"enabled": True}]
    MainScreen.open_climate_schedule_dialog(screen, schedule, on_save, on_clear)

    assert state["parent"] is screen
    assert state["schedule"] == schedule
    assert state["exec_called"] is True
    state["on_save"]([{"enabled": False}])
    state["on_clear"]()
    assert saved["dialog"] is state["dialog"]
    assert saved["rules"] == [{"enabled": False}]
    assert cleared["dialog"] is state["dialog"]


def test_open_charge_schedule_dialog_passes_callbacks_via_constructor(monkeypatch):
    state = {}

    class FakeDialog:
        def __init__(self, parent, schedule, on_save, on_clear):
            state["dialog"] = self
            state["parent"] = parent
            state["schedule"] = schedule
            state["on_save"] = on_save
            state["on_clear"] = on_clear

        def exec(self):
            state["exec_called"] = True

    monkeypatch.setattr("myhondaplus_desktop.app.ChargeScheduleDialog", FakeDialog)

    saved = {}
    cleared = {}

    def on_save(dialog, rules):
        saved["dialog"] = dialog
        saved["rules"] = rules

    def on_clear(dialog):
        cleared["dialog"] = dialog

    screen = object()
    schedule = [{"enabled": True}]
    MainScreen.open_charge_schedule_dialog(screen, schedule, on_save, on_clear)

    assert state["parent"] is screen
    assert state["schedule"] == schedule
    assert state["exec_called"] is True
    state["on_save"]([{"enabled": False}])
    state["on_clear"]()
    assert saved["dialog"] is state["dialog"]
    assert saved["rules"] == [{"enabled": False}]
    assert cleared["dialog"] is state["dialog"]


def test_entrypoint_falls_back_to_absolute_import(monkeypatch):
    fake_app = ModuleType("myhondaplus_desktop.app")
    marker = object()
    fake_app.main = marker

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "app" and level == 1:
            raise ImportError("relative import failed")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setitem(sys.modules, "myhondaplus_desktop.app", fake_app)
    monkeypatch.setattr(builtins, "__import__", fake_import)

    assert _load_main() is marker
