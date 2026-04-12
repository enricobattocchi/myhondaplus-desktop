"""Geofence management widget with interactive Leaflet map."""

from PyQt6.QtCore import QObject, QUrl, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile,
    QWebEngineUrlRequestInterceptor,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..i18n import t
from ..icons import icon

_MAP_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<style>
html, body, #map { margin: 0; padding: 0; width: 100%; height: 100%; }
</style>
</head>
<body>
<div id="map"></div>
<script>
var map = L.map('map', {center: [0, 0], zoom: 2});
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 19
}).addTo(map);

var marker = null;
var circle = null;
var bridge = null;

new QWebChannel(qt.webChannelTransport, function(channel) {
    bridge = channel.objects.bridge;
    bridge.onMapReady();
});

function setMarker(lat, lon, radiusKm) {
    var radiusM = radiusKm * 1000;
    if (marker) {
        marker.setLatLng([lat, lon]);
        circle.setLatLng([lat, lon]);
        circle.setRadius(radiusM);
    } else {
        marker = L.marker([lat, lon], {draggable: true}).addTo(map);
        circle = L.circle([lat, lon], {radius: radiusM, color: '#3388ff',
                           fillColor: '#3388ff', fillOpacity: 0.15}).addTo(map);
        marker.on('dragend', function(e) {
            var p = e.target.getLatLng();
            circle.setLatLng(p);
            if (bridge) bridge.onMarkerMoved(p.lat, p.lng);
        });
    }
    map.fitBounds(circle.getBounds().pad(0.2));
}

function setRadius(radiusKm) {
    if (circle) circle.setRadius(radiusKm * 1000);
    if (circle) map.fitBounds(circle.getBounds().pad(0.2));
}

function clearMarker() {
    if (marker) { map.removeLayer(marker); marker = null; }
    if (circle) { map.removeLayer(circle); circle = null; }
}

map.on('click', function(e) {
    var radiusM = circle ? circle.getRadius() : 1000;
    if (marker) {
        marker.setLatLng(e.latlng);
        circle.setLatLng(e.latlng);
    } else {
        marker = L.marker(e.latlng, {draggable: true}).addTo(map);
        circle = L.circle(e.latlng, {radius: radiusM, color: '#3388ff',
                           fillColor: '#3388ff', fillOpacity: 0.15}).addTo(map);
        marker.on('dragend', function(ev) {
            var p = ev.target.getLatLng();
            circle.setLatLng(p);
            if (bridge) bridge.onMarkerMoved(p.lat, p.lng);
        });
    }
    if (bridge) bridge.onMarkerMoved(e.latlng.lat, e.latlng.lng);
});
</script>
</body>
</html>"""


class _TileRequestInterceptor(QWebEngineUrlRequestInterceptor):
    """Adds Referer header to OSM tile requests."""

    def interceptRequest(self, info):
        url = info.requestUrl().toString()
        if "tile.openstreetmap.org" in url:
            info.setHttpHeader(
                b"Referer", b"https://www.openstreetmap.org/")


class _Bridge(QObject):
    """JS → Python bridge for the Leaflet map."""

    def __init__(self, widget):
        super().__init__()
        self._widget = widget

    @pyqtSlot()
    def onMapReady(self):
        self._widget._on_map_ready()

    @pyqtSlot(float, float)
    def onMarkerMoved(self, lat, lon):
        self._widget._marker_lat = lat
        self._widget._marker_lon = lon
        self._widget._coord_label.setText(f"{lat:.6f}, {lon:.6f}")


class GeofenceWidget(QWidget):
    """Geofence tab with interactive map, controls for set/clear."""

    def __init__(self, actions: dict = None):
        """
        Args:
            actions: dict of callback functions:
                on_save(lat, lon, radius, name),
                on_clear(),
                on_refresh(),
                on_use_car()
        """
        super().__init__()
        self._actions = actions or {}
        self._marker_lat = 0.0
        self._marker_lon = 0.0
        self._car_lat = None
        self._car_lon = None
        self._geofence = None
        self._map_ready = False
        self._pending_js = []

        layout = QVBoxLayout(self)

        # Map — set User-Agent and Referer per OSM tile usage policy
        from .. import __version__
        profile = QWebEngineProfile.defaultProfile()
        profile.setHttpUserAgent(
            f"myhondaplus-desktop/{__version__} (PyQt6/QWebEngine)")
        self._interceptor = _TileRequestInterceptor(self)
        profile.setUrlRequestInterceptor(self._interceptor)
        self._map = QWebEngineView()
        self._map.setMinimumHeight(350)
        self._bridge = _Bridge(self)
        self._channel = QWebChannel()
        self._channel.registerObject("bridge", self._bridge)
        self._map.page().setWebChannel(self._channel)
        self._map.setHtml(_MAP_HTML, QUrl("about:blank"))
        layout.addWidget(self._map, 1)

        # Info bar
        info = QHBoxLayout()
        info.addWidget(QLabel(t("geofence.name")))
        self._name_input = QLineEdit("Geofence")
        self._name_input.setMaximumWidth(150)
        info.addWidget(self._name_input)

        info.addWidget(QLabel(t("geofence.radius")))
        self._radius_spin = QSpinBox()
        self._radius_spin.setRange(1, 50)
        self._radius_spin.setValue(1)
        self._radius_spin.setSuffix(" km")
        self._radius_spin.valueChanged.connect(self._on_radius_changed)
        info.addWidget(self._radius_spin)

        self._coord_label = QLabel("")
        self._coord_label.setStyleSheet("color: gray;")
        info.addWidget(self._coord_label)

        info.addStretch()

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("font-weight: bold;")
        info.addWidget(self._status_label)

        layout.addLayout(info)

        # Buttons
        buttons = QHBoxLayout()
        self._car_btn = QPushButton(icon("map-pin"), t("geofence.use_car"))
        self._car_btn.clicked.connect(self._on_use_car)
        buttons.addWidget(self._car_btn)

        self._save_btn = QPushButton(icon("download"), t("geofence.save"))
        self._save_btn.clicked.connect(self._on_save)
        buttons.addWidget(self._save_btn)

        self._clear_btn = QPushButton(icon("x"), t("geofence.clear"))
        self._clear_btn.clicked.connect(self._on_clear)
        buttons.addWidget(self._clear_btn)

        self._refresh_btn = QPushButton(icon("refresh-cw"), t("geofence.refresh"))
        self._refresh_btn.clicked.connect(self._on_refresh)
        buttons.addWidget(self._refresh_btn)

        buttons.addStretch()
        layout.addLayout(buttons)

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

    def _call(self, name, *args):
        cb = self._actions.get(name)
        if cb:
            cb(*args)

    def _on_radius_changed(self, value):
        self._run_js(f"setRadius({value})")

    def _on_use_car(self):
        if self._car_lat is not None and self._car_lon is not None:
            self._marker_lat = self._car_lat
            self._marker_lon = self._car_lon
            self._coord_label.setText(
                f"{self._car_lat:.6f}, {self._car_lon:.6f}")
            radius = self._radius_spin.value()
            self._run_js(
                f"setMarker({self._car_lat}, {self._car_lon}, {radius})")

    def _on_save(self):
        if self._marker_lat == 0.0 and self._marker_lon == 0.0:
            return
        self._call("on_save", self._marker_lat, self._marker_lon,
                    self._radius_spin.value(), self._name_input.text())

    def _on_clear(self):
        if QMessageBox.question(
            self, t("commands.confirm"),
            t("geofence.clear_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self._call("on_clear")

    def _on_refresh(self):
        self._call("on_refresh")

    def set_car_location(self, lat, lon):
        self._car_lat = lat
        self._car_lon = lon

    def set_controls_enabled(self, enabled):
        self._save_btn.setEnabled(enabled)
        self._clear_btn.setEnabled(enabled)
        self._car_btn.setEnabled(enabled)
        self._refresh_btn.setEnabled(enabled)

    def set_geofence(self, geofence):
        self._geofence = geofence
        if geofence is None:
            self._status_label.setText(t("geofence.none"))
            self._status_label.setStyleSheet("color: gray; font-weight: bold;")
            self._run_js("clearMarker()")
            self._coord_label.setText("")
            return
        self._name_input.setText(geofence.name or "Geofence")
        self._radius_spin.setValue(int(geofence.radius or 1))
        self._marker_lat = geofence.latitude
        self._marker_lon = geofence.longitude
        self._coord_label.setText(
            f"{geofence.latitude:.6f}, {geofence.longitude:.6f}")
        if geofence.processing:
            self._status_label.setText(t("geofence.processing"))
            self._status_label.setStyleSheet(
                "color: #e67e22; font-weight: bold;")
        elif geofence.active:
            self._status_label.setText(t("geofence.active"))
            self._status_label.setStyleSheet(
                "color: green; font-weight: bold;")
        else:
            self._status_label.setText(t("geofence.inactive"))
            self._status_label.setStyleSheet(
                "color: gray; font-weight: bold;")
        radius = geofence.radius or 1.0
        self._run_js(
            f"setMarker({geofence.latitude}, {geofence.longitude}, {radius})")
