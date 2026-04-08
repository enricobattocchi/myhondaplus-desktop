"""Tests for trips widget month navigation."""

from datetime import date as real_date

from PyQt6.QtWidgets import QApplication

from myhondaplus_desktop.widgets.trips import TripsWidget

APP = QApplication.instance() or QApplication([])
APP.setQuitOnLastWindowClosed(False)


class FixedDate(real_date):
    @classmethod
    def today(cls):
        return cls(2026, 4, 9)


def _make_widget():
    return TripsWidget(
        get_api=lambda: object(),
        get_vin=lambda: "VIN123",
        get_vehicles=lambda: [],
        on_status=lambda message: None,
        on_error=lambda message: None,
    )


def test_next_month_is_disabled_for_current_month(monkeypatch):
    monkeypatch.setattr("myhondaplus_desktop.widgets.trips.date", FixedDate)

    widget = _make_widget()

    assert widget._current_month == FixedDate(2026, 4, 1)
    assert widget._next_btn.isEnabled() is False


def test_next_month_does_not_advance_past_current_month(monkeypatch):
    monkeypatch.setattr("myhondaplus_desktop.widgets.trips.date", FixedDate)

    widget = _make_widget()
    loads = []
    widget.load_trips = lambda: loads.append(widget._current_month)

    widget._next_month()

    assert widget._current_month == FixedDate(2026, 4, 1)
    assert loads == []
    assert widget._next_btn.isEnabled() is False


def test_prev_month_then_next_month_returns_to_current_month(monkeypatch):
    monkeypatch.setattr("myhondaplus_desktop.widgets.trips.date", FixedDate)

    widget = _make_widget()
    loads = []
    widget.load_trips = lambda: loads.append(widget._current_month)

    widget._prev_month()

    assert widget._current_month == FixedDate(2026, 3, 1)
    assert widget._next_btn.isEnabled() is True

    widget._next_month()

    assert widget._current_month == FixedDate(2026, 4, 1)
    assert widget._next_btn.isEnabled() is False
    assert loads == [FixedDate(2026, 3, 1), FixedDate(2026, 4, 1)]
