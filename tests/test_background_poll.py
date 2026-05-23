"""Tests for the BackgroundPoller.

The poller wraps two QTimer instances; tests focus on whether the right
timer is started/stopped based on Settings flags and whether intervals
are configured from the right Settings fields.
"""

from PyQt6.QtWidgets import QApplication

from myhondaplus_desktop.background_poll import BackgroundPoller
from myhondaplus_desktop.config import Settings

APP = QApplication.instance() or QApplication([])


def test_poller_with_everything_disabled_starts_nothing():
    s = Settings(
        background_poll_enabled=False,
        background_car_refresh_enabled=False,
    )
    poller = BackgroundPoller(s)
    poller.start()
    assert poller.is_running is False
    poller.stop()


def test_poller_starts_cached_timer_when_enabled():
    s = Settings(
        background_poll_enabled=True,
        background_poll_cached_interval_min=10,
        background_car_refresh_enabled=False,
    )
    poller = BackgroundPoller(s)
    poller.start()
    assert poller._cached_timer.isActive() is True
    assert poller._car_timer.isActive() is False
    # 10 minutes in ms
    assert poller._cached_timer.interval() == 10 * 60 * 1000
    poller.stop()
    assert poller.is_running is False


def test_poller_starts_car_timer_when_enabled():
    s = Settings(
        background_poll_enabled=False,
        background_car_refresh_enabled=True,
        background_car_refresh_hours=12,
    )
    poller = BackgroundPoller(s)
    poller.start()
    assert poller._cached_timer.isActive() is False
    assert poller._car_timer.isActive() is True
    # 12 hours in ms
    assert poller._car_timer.interval() == 12 * 60 * 60 * 1000
    poller.stop()


def test_poller_runs_both_timers_independently():
    s = Settings(
        background_poll_enabled=True,
        background_poll_cached_interval_min=15,
        background_car_refresh_enabled=True,
        background_car_refresh_hours=24,
    )
    poller = BackgroundPoller(s)
    poller.start()
    assert poller._cached_timer.isActive() is True
    assert poller._car_timer.isActive() is True
    assert poller._cached_timer.interval() == 15 * 60 * 1000
    assert poller._car_timer.interval() == 24 * 60 * 60 * 1000
    poller.stop()
    assert poller._cached_timer.isActive() is False
    assert poller._car_timer.isActive() is False


def test_poller_emits_signal_on_cached_timeout():
    s = Settings(background_poll_enabled=True)
    poller = BackgroundPoller(s)
    received: list[bool] = []
    poller.cached_refresh_requested.connect(lambda: received.append(True))
    # Fire the timer manually instead of waiting for real elapsed time.
    poller._cached_timer.timeout.emit()
    assert received == [True]


def test_poller_emits_signal_on_car_timeout():
    s = Settings(background_car_refresh_enabled=True)
    poller = BackgroundPoller(s)
    received: list[bool] = []
    poller.car_refresh_requested.connect(lambda: received.append(True))
    poller._car_timer.timeout.emit()
    assert received == [True]


def test_poller_stop_is_idempotent():
    s = Settings()
    poller = BackgroundPoller(s)
    poller.stop()
    poller.stop()
    assert poller.is_running is False


def test_poller_reconfigures_intervals_on_each_start():
    s = Settings(
        background_poll_enabled=True,
        background_poll_cached_interval_min=5,
    )
    poller = BackgroundPoller(s)
    poller.start()
    assert poller._cached_timer.interval() == 5 * 60 * 1000
    poller.stop()
    # Caller mutates the live Settings and starts again
    s.background_poll_cached_interval_min = 30
    poller.start()
    assert poller._cached_timer.interval() == 30 * 60 * 1000
    poller.stop()
