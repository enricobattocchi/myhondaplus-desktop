"""Tests for the NotificationDispatcher edge-detection rules."""

from myhondaplus_desktop.config import Settings
from myhondaplus_desktop.notifications import NotificationDispatcher


class FakeStatus(dict):
    """Minimal stand-in for EVStatus: a dict with ``.get()``."""


def _all_off() -> Settings:
    return Settings(
        notify_charge_started=False,
        notify_charge_stopped=False,
        notify_climate_started=False,
        notify_climate_stopped=False,
        notify_door_unlocked=False,
        notify_battery_low_pct=0,
        notify_warning_lit=False,
    )


def test_first_snapshot_fires_nothing():
    """No 'previous' means we have nothing to compare against."""
    s = Settings(
        notify_charge_stopped=True,
        notify_door_unlocked=True,
        notify_battery_low_pct=20,
        notify_warning_lit=True,
    )
    d = NotificationDispatcher(s)
    assert d.evaluate(None, FakeStatus(charge_status="charging",
                                       doors_locked=True,
                                       battery_level=50,
                                       warning_lamps=0)) == []


def test_charge_stopped_fires_on_transition():
    s = _all_off()
    s.notify_charge_stopped = True
    d = NotificationDispatcher(s)
    prev = FakeStatus(charge_status="charging", battery_level=80)
    curr = FakeStatus(charge_status="stopped", battery_level=85)
    notifs = d.evaluate(prev, curr)
    assert len(notifs) == 1
    _, body = notifs[0]
    assert "85" in body  # battery level shown in body


def test_charge_stopped_does_not_fire_if_disabled():
    s = _all_off()
    d = NotificationDispatcher(s)
    prev = FakeStatus(charge_status="charging")
    curr = FakeStatus(charge_status="stopped")
    assert d.evaluate(prev, curr) == []


def test_charge_stopped_does_not_fire_on_stable_state():
    s = _all_off()
    s.notify_charge_stopped = True
    d = NotificationDispatcher(s)
    prev = FakeStatus(charge_status="stopped")
    curr = FakeStatus(charge_status="stopped")
    assert d.evaluate(prev, curr) == []


def test_door_unlocked_fires_on_locked_to_unlocked():
    s = _all_off()
    s.notify_door_unlocked = True
    d = NotificationDispatcher(s)
    prev = FakeStatus(doors_locked=True)
    curr = FakeStatus(doors_locked=False)
    assert len(d.evaluate(prev, curr)) == 1


def test_door_unlocked_does_not_fire_on_relock():
    s = _all_off()
    s.notify_door_unlocked = True
    d = NotificationDispatcher(s)
    prev = FakeStatus(doors_locked=False)
    curr = FakeStatus(doors_locked=True)
    assert d.evaluate(prev, curr) == []


def test_battery_low_fires_when_crossing_threshold():
    s = _all_off()
    s.notify_battery_low_pct = 30
    d = NotificationDispatcher(s)
    prev = FakeStatus(battery_level=35)
    curr = FakeStatus(battery_level=25)
    notifs = d.evaluate(prev, curr)
    assert len(notifs) == 1
    _, body = notifs[0]
    assert "25" in body
    assert "30" in body


def test_battery_low_does_not_fire_when_already_below():
    s = _all_off()
    s.notify_battery_low_pct = 30
    d = NotificationDispatcher(s)
    prev = FakeStatus(battery_level=20)
    curr = FakeStatus(battery_level=15)
    assert d.evaluate(prev, curr) == []


def test_battery_low_does_not_fire_at_exact_threshold():
    s = _all_off()
    s.notify_battery_low_pct = 30
    d = NotificationDispatcher(s)
    prev = FakeStatus(battery_level=40)
    curr = FakeStatus(battery_level=30)
    # Boundary: "below" means strictly less than threshold.
    assert d.evaluate(prev, curr) == []


def test_battery_low_disabled_when_threshold_is_zero():
    s = _all_off()
    s.notify_battery_low_pct = 0
    d = NotificationDispatcher(s)
    prev = FakeStatus(battery_level=100)
    curr = FakeStatus(battery_level=5)
    assert d.evaluate(prev, curr) == []


def test_warning_lit_fires_when_lights_appear():
    s = _all_off()
    s.notify_warning_lit = True
    d = NotificationDispatcher(s)
    prev = FakeStatus(warning_lamps=0)
    curr = FakeStatus(warning_lamps=3)
    assert len(d.evaluate(prev, curr)) == 1


def test_warning_lit_handles_string_field():
    s = _all_off()
    s.notify_warning_lit = True
    d = NotificationDispatcher(s)
    prev = FakeStatus(warning_lamps="")
    curr = FakeStatus(warning_lamps="ABS,Brake")
    assert len(d.evaluate(prev, curr)) == 1


def test_warning_lit_handles_list_field():
    s = _all_off()
    s.notify_warning_lit = True
    d = NotificationDispatcher(s)
    prev = FakeStatus(warning_lamps=[])
    curr = FakeStatus(warning_lamps=["ABS"])
    assert len(d.evaluate(prev, curr)) == 1


def test_warning_lit_does_not_fire_when_clearing():
    s = _all_off()
    s.notify_warning_lit = True
    d = NotificationDispatcher(s)
    prev = FakeStatus(warning_lamps=2)
    curr = FakeStatus(warning_lamps=0)
    assert d.evaluate(prev, curr) == []


def test_charge_started_fires_on_transition():
    s = _all_off()
    s.notify_charge_started = True
    d = NotificationDispatcher(s)
    prev = FakeStatus(charge_status="not_charging", battery_level=20)
    curr = FakeStatus(charge_status="charging", battery_level=22)
    assert len(d.evaluate(prev, curr)) == 1


def test_charge_started_does_not_fire_when_already_charging():
    s = _all_off()
    s.notify_charge_started = True
    d = NotificationDispatcher(s)
    prev = FakeStatus(charge_status="charging")
    curr = FakeStatus(charge_status="charging")
    assert d.evaluate(prev, curr) == []


def test_charge_stopped_fires_on_any_exit_from_charging():
    """`charge_stopped` covers 100%, charge-limit and interruption uniformly."""
    s = _all_off()
    s.notify_charge_stopped = True
    d = NotificationDispatcher(s)
    # The library normalises Honda's chargeStatus to "stopped" for all
    # of these cases; there is no separate "complete" value.
    prev = FakeStatus(charge_status="charging")
    curr = FakeStatus(charge_status="stopped")
    assert len(d.evaluate(prev, curr)) == 1


def test_climate_started_fires_on_transition():
    s = _all_off()
    s.notify_climate_started = True
    d = NotificationDispatcher(s)
    prev = FakeStatus(climate_active=False)
    curr = FakeStatus(climate_active=True)
    assert len(d.evaluate(prev, curr)) == 1


def test_climate_stopped_fires_on_transition():
    s = _all_off()
    s.notify_climate_stopped = True
    d = NotificationDispatcher(s)
    prev = FakeStatus(climate_active=True)
    curr = FakeStatus(climate_active=False)
    assert len(d.evaluate(prev, curr)) == 1


def test_climate_started_does_not_fire_if_disabled():
    s = _all_off()
    d = NotificationDispatcher(s)
    prev = FakeStatus(climate_active=False)
    curr = FakeStatus(climate_active=True)
    assert d.evaluate(prev, curr) == []


def test_multiple_rules_fire_independently():
    s = Settings(
        notify_charge_stopped=True,
        notify_door_unlocked=True,
    )
    d = NotificationDispatcher(s)
    prev = FakeStatus(charge_status="charging", doors_locked=True)
    curr = FakeStatus(charge_status="stopped", doors_locked=False)
    notifs = d.evaluate(prev, curr)
    assert len(notifs) == 2


def test_no_status_does_not_crash():
    s = Settings(notify_charge_stopped=True)
    d = NotificationDispatcher(s)
    assert d.evaluate(None, None) == []
    assert d.evaluate(FakeStatus(charge_status="charging"), None) == []
