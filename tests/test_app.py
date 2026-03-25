"""Tests for app helpers."""

from myhondaplus_desktop.app import _vehicle_label


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
