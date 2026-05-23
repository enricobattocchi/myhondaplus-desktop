"""Tests for the TrayController.

The behaviour we care about:
- When the platform has no system tray, the controller falls back to a
  no-op (``available`` is False, no QSystemTrayIcon is created).
- When the platform has a tray, signals get wired to menu actions.
- The toggle action label reflects the current window-visibility state.
- The activation handler emits ``show_window_requested`` only for plain
  click activations and never on macOS (where Qt opens the menu itself).
"""

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon

from myhondaplus_desktop import tray as tray_mod
from myhondaplus_desktop.tray import TrayController

APP = QApplication.instance() or QApplication([])


def test_no_tray_when_system_tray_unavailable(monkeypatch):
    monkeypatch.setattr(
        QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: False))
    controller = TrayController()
    assert controller.available is False
    # No icon created → calling show/hide must be no-ops, not raise.
    controller.show()
    controller.hide()
    controller.set_window_visible(True)
    controller.set_vehicle_name("Lopomobile")


def test_tray_built_when_system_tray_available(monkeypatch):
    monkeypatch.setattr(
        QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    controller = TrayController()
    assert controller.available is True
    assert controller._tray is not None
    assert controller._menu is not None
    # Menu has: toggle, vehicle submenu (hidden by default), separator,
    # settings, quit — 4 non-separator entries.
    actions = controller._menu.actions()
    assert len([a for a in actions if not a.isSeparator()]) == 4


def test_set_window_visible_toggles_action_label(monkeypatch):
    monkeypatch.setattr(
        QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    controller = TrayController()
    assert controller._toggle_action is not None
    controller.set_window_visible(True)
    hidden_label = controller._toggle_action.text()
    controller.set_window_visible(False)
    shown_label = controller._toggle_action.text()
    assert hidden_label != shown_label


def test_set_vehicle_name_updates_tooltip(monkeypatch):
    monkeypatch.setattr(
        QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    controller = TrayController()
    controller.set_vehicle_name("Lopomobile")
    assert controller._tray is not None
    assert controller._tray.toolTip() == "Lopomobile"


def test_signals_wired_to_menu_actions(monkeypatch):
    monkeypatch.setattr(
        QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    controller = TrayController()
    events: list[str] = []
    controller.show_window_requested.connect(lambda: events.append("show"))
    controller.settings_requested.connect(lambda: events.append("settings"))
    controller.quit_requested.connect(lambda: events.append("quit"))
    # Skip the hidden vehicle submenu (a menu, not a leaf action).
    actions = [a for a in controller._menu.actions()
               if not a.isSeparator() and a is not controller._vehicle_submenu_action]
    for action in actions:
        action.trigger()
    assert events == ["show", "settings", "quit"]


def test_set_vehicles_hides_submenu_when_single_vehicle(monkeypatch):
    monkeypatch.setattr(
        QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    controller = TrayController()
    controller.set_vehicles([{"vin": "VIN1", "name": "Lopomobile"}], "VIN1")
    assert controller._vehicle_submenu_action.isVisible() is False


def test_set_vehicles_populates_submenu_for_multiple(monkeypatch):
    monkeypatch.setattr(
        QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    controller = TrayController()
    controller.set_vehicles(
        [
            {"vin": "VIN1", "name": "Lopomobile"},
            {"vin": "VIN2", "name": "Spare"},
        ],
        "VIN1",
    )
    assert controller._vehicle_submenu_action.isVisible() is True
    items = controller._vehicle_submenu.actions()
    assert [a.text() for a in items] == ["Lopomobile", "Spare"]
    assert items[0].isChecked() is True
    assert items[1].isChecked() is False


def test_set_vehicles_emits_signal_on_pick(monkeypatch):
    monkeypatch.setattr(
        QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    controller = TrayController()
    picked: list[str] = []
    controller.vehicle_selected.connect(picked.append)
    controller.set_vehicles(
        [
            {"vin": "VIN1", "name": "A"},
            {"vin": "VIN2", "name": "B"},
        ],
        "VIN1",
    )
    items = controller._vehicle_submenu.actions()
    items[1].trigger()
    assert picked == ["VIN2"]


def test_activated_emits_show_on_linux(monkeypatch):
    monkeypatch.setattr(
        QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    monkeypatch.setattr(tray_mod, "click_opens_menu", lambda: False)
    controller = TrayController()
    events: list[str] = []
    controller.show_window_requested.connect(lambda: events.append("show"))
    controller._on_activated(QSystemTrayIcon.ActivationReason.Trigger)
    assert events == ["show"]


def test_activated_is_noop_on_macos(monkeypatch):
    monkeypatch.setattr(
        QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    monkeypatch.setattr(tray_mod, "click_opens_menu", lambda: True)
    controller = TrayController()
    events: list[str] = []
    controller.show_window_requested.connect(lambda: events.append("show"))
    controller._on_activated(QSystemTrayIcon.ActivationReason.Trigger)
    assert events == []


def test_activated_ignores_non_trigger_reasons(monkeypatch):
    monkeypatch.setattr(
        QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    monkeypatch.setattr(tray_mod, "click_opens_menu", lambda: False)
    controller = TrayController()
    events: list[str] = []
    controller.show_window_requested.connect(lambda: events.append("show"))
    controller._on_activated(QSystemTrayIcon.ActivationReason.Context)
    controller._on_activated(QSystemTrayIcon.ActivationReason.MiddleClick)
    controller._on_activated(QSystemTrayIcon.ActivationReason.DoubleClick)
    assert events == []
