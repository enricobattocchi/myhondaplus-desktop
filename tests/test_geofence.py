"""Tests for the geofence tile-map math functions."""

from myhondaplus_desktop.widgets.geofence import (
    _km_to_scene_pixels,
    _lat_lon_to_scene,
    _lat_lon_to_tile,
    _scene_to_lat_lon,
    _tile_to_lat_lon,
    _zoom_to_fit_radius,
)


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
