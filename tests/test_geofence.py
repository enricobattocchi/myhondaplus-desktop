"""Tests for the geofence widget and tile-map math functions."""

from PyQt6.QtWidgets import QApplication, QComboBox

from myhondaplus_desktop.widgets.geofence import (
    _KM_PER_MILE,
    GeofenceWidget,
    _km_to_scene_pixels,
    _lat_lon_to_scene,
    _lat_lon_to_tile,
    _scene_to_lat_lon,
    _tile_to_lat_lon,
    _zoom_to_fit_radius,
)

APP = QApplication.instance() or QApplication([])
APP.setQuitOnLastWindowClosed(False)


class FakeGeofence:
    def __init__(self, radius=1.0, latitude=44.0, longitude=11.0,
                 name="Geofence", active=True,
                 waiting_activate=False, waiting_deactivate=False):
        self.radius = radius
        self.latitude = latitude
        self.longitude = longitude
        self.name = name
        self.active = active
        self.waiting_activate = waiting_activate
        self.waiting_deactivate = waiting_deactivate


class FakeMap:
    """Records calls so widget logic can be asserted without a real map."""

    def __init__(self):
        self.markers = []
        self.radii = []
        self.cleared = 0
        self._has_marker = False

    def set_marker(self, lat, lon, radius_km):
        self.markers.append((lat, lon, radius_km))
        self._has_marker = True

    def set_radius(self, radius_km):
        self.radii.append(radius_km)

    def clear_marker(self):
        self.cleared += 1
        self._has_marker = False

    def has_marker(self):
        return self._has_marker


def _widget(actions=None):
    w = GeofenceWidget(actions=actions)
    w._map = FakeMap()
    return w


# -- Tile/scene math --

def test_lat_lon_to_tile_center():
    x, y = _lat_lon_to_tile(0, 0, 0)
    assert x == 0.5
    assert abs(y - 0.5) < 0.001


def test_lat_lon_tile_roundtrip():
    lat, lon = 45.0, 10.0
    for zoom in [5, 10, 15]:
        tx, ty = _lat_lon_to_tile(lat, lon, zoom)
        lat2, lon2 = _tile_to_lat_lon(tx, ty, zoom)
        assert abs(lat - lat2) < 0.0001
        assert abs(lon - lon2) < 0.0001


def test_scene_roundtrip():
    lat, lon, zoom = 48.8566, 2.3522, 12
    sx, sy = _lat_lon_to_scene(lat, lon, zoom)
    lat2, lon2 = _scene_to_lat_lon(sx, sy, zoom)
    assert abs(lat - lat2) < 0.0001
    assert abs(lon - lon2) < 0.0001


def test_km_to_pixels_larger_at_higher_zoom():
    px_z10 = _km_to_scene_pixels(45.0, 1.0, 10)
    px_z15 = _km_to_scene_pixels(45.0, 1.0, 15)
    assert px_z15 > px_z10


def test_zoom_to_fit_radius():
    z = _zoom_to_fit_radius(45.0, 5.0, 600)
    assert 2 <= z <= 18


# -- Radius combo options --

def test_radius_combo_km_options():
    w = _widget()
    combo = w._radius_combo
    assert isinstance(combo, QComboBox)
    assert not combo.isEditable()
    assert combo.count() == 5
    labels = [combo.itemText(i) for i in range(combo.count())]
    assert labels == ["1 km", "5 km", "10 km", "20 km", "30 km"]
    values = [combo.itemData(i) for i in range(combo.count())]
    assert values == [1.0, 5.0, 10.0, 20.0, 30.0]


def test_radius_combo_miles_options():
    w = _widget()
    w.set_distance_unit("miles")
    combo = w._radius_combo
    labels = [combo.itemText(i) for i in range(5)]
    assert labels == ["0.5 mi", "1 mi", "5 mi", "10 mi", "20 mi"]
    values = [combo.itemData(i) for i in range(5)]
    assert values == [0.8, 1.6, 8.0, 16.1, 32.2]
    # The default 1.0 km selection matches no mile option, so it survives
    # the unit switch as a custom entry.
    assert combo.count() == 6
    assert combo.currentData() == 1.0


def test_default_unit_is_km():
    w = _widget()
    labels = [w._radius_combo.itemText(i)
              for i in range(w._radius_combo.count())]
    assert all(label.endswith(" km") for label in labels)


# -- Existing geofence rendering --

def test_set_geofence_standard_radius_selects_option():
    w = _widget()
    w.set_geofence(FakeGeofence(radius=10.0))
    assert w._radius_combo.count() == 5
    assert w._radius_combo.currentData() == 10.0


def test_set_geofence_custom_radius_adds_entry():
    w = _widget()
    w.set_geofence(FakeGeofence(radius=2.5))
    combo = w._radius_combo
    assert combo.count() == 6
    assert combo.currentIndex() == 5
    assert combo.currentData() == 2.5
    assert combo.currentText() == "2.5 km"


def test_tolerance_matching():
    w = _widget()
    w.set_geofence(FakeGeofence(radius=10.04))
    assert w._radius_combo.count() == 5
    assert w._radius_combo.currentData() == 10.0
    w.set_geofence(FakeGeofence(radius=10.06))
    assert w._radius_combo.count() == 6
    assert w._radius_combo.currentData() == 10.06


def test_custom_entry_removed_after_standard_read():
    w = _widget()
    w.set_geofence(FakeGeofence(radius=2.5))
    assert w._radius_combo.count() == 6
    w.set_geofence(FakeGeofence(radius=5.0))
    assert w._radius_combo.count() == 5
    assert w._radius_combo.currentData() == 5.0


def test_unit_flip_after_custom_entry():
    w = _widget()
    # 1.6 km is custom in km mode but matches the "1 mi" option exactly.
    w.set_geofence(FakeGeofence(radius=1.6))
    assert w._radius_combo.count() == 6
    w.set_distance_unit("miles")
    assert w._radius_combo.count() == 5
    assert w._radius_combo.currentText() == "1 mi"
    assert w._radius_combo.currentData() == 1.6
    w.set_distance_unit("km")
    assert w._radius_combo.count() == 6
    assert w._radius_combo.currentText() == "1.6 km"
    assert w._radius_combo.currentData() == 1.6


def test_set_geofence_passes_km_float_to_map():
    w = _widget()
    w.set_geofence(FakeGeofence(radius=2.5, latitude=44.0, longitude=11.0))
    assert w._map.markers[-1] == (44.0, 11.0, 2.5)


# -- Save flow --

def test_save_uses_existing_geofence_center():
    calls = []
    w = _widget({"on_save": lambda *a: calls.append(a)})
    w.set_geofence(FakeGeofence(radius=5.0, latitude=44.0, longitude=11.0))
    w.set_car_location(50.0, 8.0)
    w._on_save()
    assert calls == [(44.0, 11.0, 5.0, "Geofence")]


def test_save_uses_car_location_when_no_geofence():
    calls = []
    w = _widget({"on_save": lambda *a: calls.append(a)})
    w.set_car_location(50.0, 8.0)
    w._radius_combo.setCurrentIndex(1)  # 5 km
    w._on_save()
    assert calls == [(50.0, 8.0, 5.0, "Geofence")]


def test_save_disabled_without_car_and_geofence():
    calls = []
    w = _widget({"on_save": lambda *a: calls.append(a)})
    assert not w._save_btn.isEnabled()
    w._on_save()
    assert calls == []
    w.set_car_location(50.0, 8.0)
    assert w._save_btn.isEnabled()


def test_set_controls_enabled_respects_save_gating():
    w = _widget()
    w.set_controls_enabled(False)
    w.set_car_location(50.0, 8.0)
    assert not w._save_btn.isEnabled()
    w.set_controls_enabled(True)
    assert w._save_btn.isEnabled()
    w2 = _widget()
    w2.set_controls_enabled(False)
    w2.set_controls_enabled(True)
    # No car location and no geofence: still not saveable.
    assert not w2._save_btn.isEnabled()


def test_radius_only_save_with_geofence_no_car_location():
    calls = []
    w = _widget({"on_save": lambda *a: calls.append(a)})
    w.set_geofence(FakeGeofence(radius=5.0, latitude=44.0, longitude=11.0))
    assert w._save_btn.isEnabled()
    w._radius_combo.setCurrentIndex(2)  # 10 km
    w._on_save()
    assert calls == [(44.0, 11.0, 10.0, "Geofence")]


def test_save_in_miles_sends_rounded_km():
    calls = []
    w = _widget({"on_save": lambda *a: calls.append(a)})
    w.set_distance_unit("miles")
    w.set_car_location(50.0, 8.0)
    w._radius_combo.setCurrentIndex(3)  # 10 mi
    w._on_save()
    assert calls == [(50.0, 8.0, 16.1, "Geofence")]
    assert calls[0][2] == round(10 * _KM_PER_MILE, 1)


# -- Car location preview --

def test_car_location_preview_only_without_geofence():
    w = _widget()
    w.set_car_location(50.0, 8.0)
    assert w._map.markers == [(50.0, 8.0, 1.0)]
    # Same position again: no map re-centering.
    w.set_car_location(50.0, 8.0)
    assert len(w._map.markers) == 1
    # Car moved: preview follows.
    w.set_car_location(50.1, 8.1)
    assert w._map.markers[-1] == (50.1, 8.1, 1.0)
    # With a geofence set, car updates never touch the map.
    w.set_geofence(FakeGeofence(latitude=44.0, longitude=11.0))
    count = len(w._map.markers)
    w.set_car_location(51.0, 9.0)
    assert len(w._map.markers) == count


def test_set_geofence_none_resets():
    w = _widget()
    w.set_geofence(FakeGeofence(radius=2.5))
    w.set_geofence(None)
    assert w._radius_combo.count() == 5
    assert w._map.cleared == 1
    assert w._coord_label.text() == ""
    assert not w._save_btn.isEnabled()


def test_set_geofence_none_previews_car_when_known():
    w = _widget()
    w.set_car_location(50.0, 8.0)
    w.set_geofence(FakeGeofence(radius=5.0, latitude=44.0, longitude=11.0))
    w.set_geofence(None)
    assert w._map.markers[-1] == (50.0, 8.0, 1.0)
    assert w._coord_label.text() == "50.000000, 8.000000"
    assert w._save_btn.isEnabled()


# -- Removed interactions --

def test_widget_has_no_marker_interaction():
    w = GeofenceWidget()
    assert not hasattr(w, "_car_btn")
    assert not hasattr(w._map, "on_marker_moved")
