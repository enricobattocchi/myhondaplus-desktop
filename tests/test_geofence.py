"""Tests for the geofence widget JS queueing logic."""

from unittest.mock import MagicMock


class FakePage:
    def __init__(self):
        self.js_calls = []

    def runJavaScript(self, code):
        self.js_calls.append(code)


def _make_widget():
    """Create a GeofenceWidget-like object with just the JS queueing logic."""

    class Widget:
        def __init__(self):
            self._map = MagicMock()
            self._map.page.return_value = FakePage()
            self._map_ready = False
            self._pending_js = []
            self._marker_lat = 0.0
            self._marker_lon = 0.0
            self._car_lat = None
            self._car_lon = None

        def _run_js(self, code):
            if self._map_ready:
                self._map.page().runJavaScript(code)
            else:
                self._pending_js.append(code)

        def _on_map_ready(self):
            self._map_ready = True
            pending = list(self._pending_js)
            self._pending_js.clear()
            for code in pending:
                self._map.page().runJavaScript(code)

    return Widget()


def test_run_js_queues_before_map_ready():
    w = _make_widget()
    assert w._map_ready is False
    w._run_js("setMarker(1, 2, 3)")
    w._run_js("setRadius(5)")
    assert w._pending_js == ["setMarker(1, 2, 3)", "setRadius(5)"]
    assert w._map.page().js_calls == []


def test_run_js_executes_after_map_ready():
    w = _make_widget()
    w._on_map_ready()
    assert w._map_ready is True
    w._run_js("setMarker(1, 2, 3)")
    assert w._map.page().js_calls == ["setMarker(1, 2, 3)"]
    assert w._pending_js == []


def test_on_map_ready_replays_pending_js():
    w = _make_widget()
    w._run_js("setMarker(1, 2, 3)")
    w._run_js("setRadius(5)")
    assert len(w._map.page().js_calls) == 0
    w._on_map_ready()
    assert w._map.page().js_calls == ["setMarker(1, 2, 3)", "setRadius(5)"]
    assert w._pending_js == []


def test_pending_cleared_after_replay():
    w = _make_widget()
    w._run_js("a()")
    w._run_js("b()")
    w._on_map_ready()
    # After replay, new calls go directly
    w._run_js("c()")
    assert w._map.page().js_calls == ["a()", "b()", "c()"]
    assert w._pending_js == []
