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


def test_battery_template_icon_is_mask_flagged():
    icon = tray_mod._battery_template_icon(50, low=False)
    assert icon.isMask() is True
    assert not icon.isNull()


def test_tray_icon_name_picks_silhouette_on_macos(monkeypatch):
    """`app-icon.svg` has an opaque rounded-square background, which
    breaks macOS template images (the alpha is opaque everywhere, so
    the menu bar paints a solid filled rectangle). The macOS path must
    pick the alpha-clean Lucide car silhouette instead."""
    monkeypatch.setattr(tray_mod, "is_macos", lambda: True)
    assert tray_mod._tray_icon_name() == "car"
    monkeypatch.setattr(tray_mod, "is_macos", lambda: False)
    assert tray_mod._tray_icon_name() == "app-icon"


def test_build_icon_on_macos_uses_silhouette_and_flags_mask(monkeypatch):
    monkeypatch.setattr(
        QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    monkeypatch.setattr(tray_mod, "is_macos", lambda: True)
    requested: list[str] = []
    real_load = tray_mod.load_icon

    def spy_load(name):
        requested.append(name)
        return real_load(name)

    monkeypatch.setattr(tray_mod, "load_icon", spy_load)
    controller = TrayController()
    assert "car" in requested
    assert "app-icon" not in requested
    assert controller._tray.icon().isMask() is True


def test_battery_template_low_glyph_adds_opaque_pixels():
    """The exclamation glyph should add opaque pixels to the canvas;
    counting (rather than per-pixel probing) avoids picking a pixel that
    might be inside the base car icon's footprint."""
    size = 64
    normal = tray_mod._render_battery_template(50, size, low=False).toImage()
    low = tray_mod._render_battery_template(50, size, low=True).toImage()

    def opaque_count(img):
        return sum(
            img.pixelColor(x, y).alpha() == 255
            for x in range(img.width())
            for y in range(img.height())
        )

    # The glyph is well over a dozen opaque pixels at this size.
    assert opaque_count(low) > opaque_count(normal) + 10


def _fake_icon():
    from PyQt6.QtGui import QIcon
    return QIcon()


def _tripwire_factory(label):
    def boom(*_a, **_kw):
        raise AssertionError(f"{label} should not run on this platform")
    return boom


def test_set_status_summary_uses_template_icon_on_macos(monkeypatch):
    monkeypatch.setattr(
        QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    monkeypatch.setattr(tray_mod, "is_macos", lambda: True)
    template_calls: list[tuple[int, bool]] = []

    def fake_template(pct, low):
        template_calls.append((pct, low))
        return _fake_icon()

    monkeypatch.setattr(tray_mod, "_battery_template_icon", fake_template)
    monkeypatch.setattr(
        tray_mod, "_battery_bar_icon",
        _tripwire_factory("colored bar"))
    controller = TrayController()
    controller.set_status_summary(battery_pct=15, low_pct=20)
    controller.set_status_summary(battery_pct=80, low_pct=20)
    assert template_calls == [(15, True), (80, False)]


def test_set_status_summary_uses_colored_bar_on_linux(monkeypatch):
    monkeypatch.setattr(
        QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    monkeypatch.setattr(tray_mod, "is_macos", lambda: False)
    bar_calls: list[int] = []

    def fake_bar(pct):
        bar_calls.append(pct)
        return _fake_icon()

    monkeypatch.setattr(tray_mod, "_battery_bar_icon", fake_bar)
    monkeypatch.setattr(
        tray_mod, "_battery_template_icon",
        _tripwire_factory("template icon"))
    controller = TrayController()
    controller.set_status_summary(battery_pct=42, low_pct=20)
    assert bar_calls == [42]


def test_set_status_summary_no_low_glyph_when_threshold_disabled(monkeypatch):
    """low_pct=0 (notifications off) must never trigger the low glyph."""
    monkeypatch.setattr(
        QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    monkeypatch.setattr(tray_mod, "is_macos", lambda: True)
    calls: list[tuple[int, bool]] = []

    def fake_template(pct, low):
        calls.append((pct, low))
        return _fake_icon()

    monkeypatch.setattr(tray_mod, "_battery_template_icon", fake_template)
    monkeypatch.setattr(
        tray_mod, "_battery_bar_icon",
        _tripwire_factory("colored bar"))
    controller = TrayController()
    controller.set_status_summary(battery_pct=5, low_pct=0)
    assert calls == [(5, False)]
