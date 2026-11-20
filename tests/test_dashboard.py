"""Tests for dashboard helpers."""

from myhondaplus_desktop.widgets.dashboard import _dms_to_decimal, _format_temp


def test_dms_to_decimal_basic():
    result = _dms_to_decimal("43,33,11.794")
    assert result is not None
    assert abs(result - 43.553276) < 0.0001


def test_dms_to_decimal_longitude():
    result = _dms_to_decimal("10,19,56.770")
    assert result is not None
    assert abs(result - 10.332436) < 0.0001


def test_dms_to_decimal_plain_float():
    result = _dms_to_decimal("45.4642")
    assert result is not None
    assert abs(result - 45.4642) < 0.0001


def test_dms_to_decimal_invalid():
    assert _dms_to_decimal("") is None
    assert _dms_to_decimal("abc") is None
    assert _dms_to_decimal(None) is None


def test_dms_to_decimal_zero():
    result = _dms_to_decimal("0,0,0.0")
    assert result is not None
    assert result == 0.0


def test_format_temp_with_value():
    assert _format_temp(21, "\u00b0C") == "21\u00b0C"
    assert _format_temp(0, "\u00b0F") == "0\u00b0F"


def test_format_temp_missing_shows_dash():
    assert _format_temp(None, "\u00b0C") == "\u2014"
    assert _format_temp("", "\u00b0C") == "\u2014"
