"""Geofence management widget with native tile map."""

import math

from PyQt6.QtCore import QPointF, Qt, QUrl
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
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

_TILE_SIZE = 256


def _lat_lon_to_tile(lat, lon, zoom):
    """Convert lat/lon to fractional tile coordinates at given zoom."""
    n = 2 ** zoom
    x = (lon + 180.0) / 360.0 * n
    lat_rad = math.radians(lat)
    y = (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad))
         / math.pi) / 2.0 * n
    return x, y


def _tile_to_lat_lon(x, y, zoom):
    """Convert tile coordinates back to lat/lon."""
    n = 2 ** zoom
    lon = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat = math.degrees(lat_rad)
    return lat, lon


def _lat_lon_to_scene(lat, lon, zoom):
    """Convert lat/lon to scene pixel position at given zoom."""
    tx, ty = _lat_lon_to_tile(lat, lon, zoom)
    return tx * _TILE_SIZE, ty * _TILE_SIZE


def _scene_to_lat_lon(sx, sy, zoom):
    """Convert scene pixel coordinates to lat/lon."""
    return _tile_to_lat_lon(sx / _TILE_SIZE, sy / _TILE_SIZE, zoom)


def _km_to_scene_pixels(lat, km, zoom):
    """Convert km to scene pixels at given latitude and zoom."""
    meters_per_pixel = (156543.03392 * math.cos(math.radians(lat))
                        / (2 ** zoom))
    if meters_per_pixel == 0:
        return 0
    return (km * 1000) / meters_per_pixel


def _zoom_to_fit_radius(lat, radius_km, view_pixels):
    """Find zoom level where the circle diameter fits in view_pixels."""
    for z in range(18, 1, -1):
        px = _km_to_scene_pixels(lat, radius_km, z)
        if px * 2 * 1.4 < view_pixels:
            return z
    return 2


class _TileMapView(QGraphicsView):
    """Slippy map widget using OSM tiles in a QGraphicsScene."""

    _ZOOM_MIN = 2
    _ZOOM_MAX = 18
    _MARKER_RADIUS = 7
    _DRAG_THRESHOLD = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumHeight(350)

        from .. import __version__
        self._user_agent = (
            f"myhondaplus-desktop/{__version__} (PyQt6)").encode()
        self._nam = QNetworkAccessManager(self)
        self._tile_cache: dict[tuple[int, int, int], QPixmap] = {}
        self._tile_items: dict[tuple[int, int, int], QGraphicsPixmapItem] = {}
        self._pending: set[tuple[int, int, int]] = set()

        self._zoom = 2
        self._marker_item: QGraphicsEllipseItem | None = None
        self._circle_item: QGraphicsEllipseItem | None = None
        self._marker_lat = 0.0
        self._marker_lon = 0.0
        self._radius_km = 1.0

        self._dragging_marker = False
        self._panning = False
        self._press_pos = QPointF()
        self._press_scene_pos = QPointF()

        self.on_marker_moved = None  # callback(lat, lon)

        # Attribution overlay
        self._attr_label = QLabel(
            "\u00a9 OpenStreetMap contributors", self)
        self._attr_label.setStyleSheet(
            "background: rgba(255,255,255,180); color: #333; "
            "font-size: 10px; padding: 1px 4px;")
        self._attr_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # Initial tiles
        self._center_scene = QPointF(
            *_lat_lon_to_scene(0, 0, self._zoom))
        self._load_visible_tiles()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._load_visible_tiles()
        a = self._attr_label
        a.adjustSize()
        a.move(self.width() - a.width() - 4, self.height() - a.height() - 4)

    def _load_visible_tiles(self):
        vr = self.mapToScene(self.viewport().rect()).boundingRect()
        x0 = max(0, int(vr.left() / _TILE_SIZE))
        y0 = max(0, int(vr.top() / _TILE_SIZE))
        x1 = int(vr.right() / _TILE_SIZE)
        y1 = int(vr.bottom() / _TILE_SIZE)
        max_tile = 2 ** self._zoom - 1
        for tx in range(x0, min(x1 + 1, max_tile + 1)):
            for ty in range(y0, min(y1 + 1, max_tile + 1)):
                key = (self._zoom, tx, ty)
                if key in self._tile_items:
                    continue
                if key in self._tile_cache:
                    self._add_tile_item(key, self._tile_cache[key])
                elif key not in self._pending:
                    self._fetch_tile(*key)

    def _add_tile_item(self, key, pixmap):
        _, tx, ty = key
        item = QGraphicsPixmapItem(pixmap)
        item.setPos(tx * _TILE_SIZE, ty * _TILE_SIZE)
        item.setZValue(0)
        self._scene.addItem(item)
        self._tile_items[key] = item

    def _fetch_tile(self, z, x, y):
        key = (z, x, y)
        self._pending.add(key)
        url = QUrl(f"https://tile.openstreetmap.org/{z}/{x}/{y}.png")
        req = QNetworkRequest(url)
        req.setRawHeader(b"User-Agent", self._user_agent)
        req.setRawHeader(b"Referer", b"https://www.openstreetmap.org/")
        reply = self._nam.get(req)
        reply.finished.connect(lambda: self._on_tile_loaded(key, reply))

    def _on_tile_loaded(self, key, reply):
        self._pending.discard(key)
        z = key[0]
        if reply.error().value != 0 or z != self._zoom:
            reply.deleteLater()
            return
        data = reply.readAll()
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        self._tile_cache[key] = pixmap
        if z == self._zoom and key not in self._tile_items:
            self._add_tile_item(key, pixmap)
        reply.deleteLater()

    def _rebuild_scene(self):
        """Clear scene and re-add everything for current zoom."""
        self._scene.clear()
        self._tile_items.clear()
        self._marker_item = None
        self._circle_item = None
        self._pending.clear()
        # Set scene rect to the full world at this zoom so centerOn can
        # scroll anywhere before tiles have loaded.
        world = 2 ** self._zoom * _TILE_SIZE
        self._scene.setSceneRect(0, 0, world, world)
        self._load_visible_tiles()

    def _update_overlay(self):
        """Re-add marker and circle at current zoom."""
        if self._marker_lat == 0.0 and self._marker_lon == 0.0:
            return
        cx, cy = _lat_lon_to_scene(
            self._marker_lat, self._marker_lon, self._zoom)
        rpx = _km_to_scene_pixels(
            self._marker_lat, self._radius_km, self._zoom)

        # Circle
        self._circle_item = QGraphicsEllipseItem(
            cx - rpx, cy - rpx, rpx * 2, rpx * 2)
        self._circle_item.setPen(QPen(QColor("#3388ff"), 2))
        self._circle_item.setBrush(QBrush(QColor(51, 136, 255, 38)))
        self._circle_item.setZValue(1)
        self._scene.addItem(self._circle_item)

        # Marker dot
        r = self._MARKER_RADIUS
        self._marker_item = QGraphicsEllipseItem(
            cx - r, cy - r, r * 2, r * 2)
        self._marker_item.setPen(QPen(QColor("#2255aa"), 2))
        self._marker_item.setBrush(QBrush(QColor("#3388ff")))
        self._marker_item.setZValue(2)
        self._scene.addItem(self._marker_item)

    # -- Public API used by GeofenceWidget --

    def set_marker(self, lat, lon, radius_km):
        self._marker_lat = lat
        self._marker_lon = lon
        self._radius_km = radius_km
        view_px = min(self.viewport().width(), self.viewport().height())
        self._zoom = _zoom_to_fit_radius(lat, radius_km, view_px or 400)
        self._rebuild_scene()
        self._update_overlay()
        cx, cy = _lat_lon_to_scene(lat, lon, self._zoom)
        self.centerOn(cx, cy)
        self._load_visible_tiles()

    def set_radius(self, radius_km):
        self._radius_km = radius_km
        if self._marker_lat == 0.0 and self._marker_lon == 0.0:
            return
        view_px = min(self.viewport().width(), self.viewport().height())
        self._zoom = _zoom_to_fit_radius(
            self._marker_lat, radius_km, view_px or 400)
        self._rebuild_scene()
        self._update_overlay()
        cx, cy = _lat_lon_to_scene(
            self._marker_lat, self._marker_lon, self._zoom)
        self.centerOn(cx, cy)
        self._load_visible_tiles()

    def clear_marker(self):
        if self._marker_item:
            self._scene.removeItem(self._marker_item)
            self._marker_item = None
        if self._circle_item:
            self._scene.removeItem(self._circle_item)
            self._circle_item = None
        self._marker_lat = 0.0
        self._marker_lon = 0.0

    # -- Mouse interactions --

    def _marker_hit(self, scene_pos):
        if self._marker_item is None:
            return False
        mc = self._marker_item.rect().center()
        dx = scene_pos.x() - mc.x()
        dy = scene_pos.y() - mc.y()
        return (dx * dx + dy * dy) < (self._MARKER_RADIUS + 8) ** 2

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        self._press_pos = event.position()
        self._press_scene_pos = self.mapToScene(event.position().toPoint())
        if self._marker_hit(self._press_scene_pos):
            self._dragging_marker = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        else:
            self._panning = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._dragging_marker:
            sp = self.mapToScene(event.position().toPoint())
            cx, cy = sp.x(), sp.y()
            r = self._MARKER_RADIUS
            self._marker_item.setRect(cx - r, cy - r, r * 2, r * 2)
            if self._circle_item:
                rpx = _km_to_scene_pixels(
                    self._marker_lat, self._radius_km, self._zoom)
                self._circle_item.setRect(
                    cx - rpx, cy - rpx, rpx * 2, rpx * 2)
        elif self._panning:
            delta = event.position() - self._press_pos
            self._press_pos = event.position()
            hs = self.horizontalScrollBar()
            vs = self.verticalScrollBar()
            hs.setValue(hs.value() - int(delta.x()))
            vs.setValue(vs.value() - int(delta.y()))
            self._load_visible_tiles()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mouseReleaseEvent(event)
        release_pos = event.position()
        was_dragging = self._dragging_marker
        was_panning = self._panning
        self._dragging_marker = False
        self._panning = False
        self.setCursor(Qt.CursorShape.ArrowCursor)

        if was_dragging:
            sp = self.mapToScene(release_pos.toPoint())
            lat, lon = _scene_to_lat_lon(sp.x(), sp.y(), self._zoom)
            self._marker_lat = lat
            self._marker_lon = lon
            if self.on_marker_moved:
                self.on_marker_moved(lat, lon)
        elif was_panning:
            self._load_visible_tiles()
            # Check if it was actually a click (minimal movement)
            sp_release = self.mapToScene(release_pos.toPoint())
            dx = sp_release.x() - self._press_scene_pos.x()
            dy = sp_release.y() - self._press_scene_pos.y()
            if abs(dx) < self._DRAG_THRESHOLD and abs(dy) < self._DRAG_THRESHOLD:
                self._place_marker_at(sp_release)
        else:
            super().mouseReleaseEvent(event)

    def _place_marker_at(self, scene_pos):
        lat, lon = _scene_to_lat_lon(
            scene_pos.x(), scene_pos.y(), self._zoom)
        self._marker_lat = lat
        self._marker_lon = lon
        # Remove old overlay items
        if self._marker_item:
            self._scene.removeItem(self._marker_item)
            self._marker_item = None
        if self._circle_item:
            self._scene.removeItem(self._circle_item)
            self._circle_item = None
        self._update_overlay()
        if self.on_marker_moved:
            self.on_marker_moved(lat, lon)

    def wheelEvent(self, event):
        # Preserve the current viewport center across zoom changes
        old_center = self.mapToScene(self.viewport().rect().center())
        old_zoom = self._zoom
        delta = event.angleDelta().y()
        if delta > 0 and self._zoom < self._ZOOM_MAX:
            self._zoom += 1
        elif delta < 0 and self._zoom > self._ZOOM_MIN:
            self._zoom -= 1
        else:
            return
        lat, lon = _scene_to_lat_lon(
            old_center.x(), old_center.y(), old_zoom)
        self._rebuild_scene()
        self._update_overlay()
        new_center = QPointF(*_lat_lon_to_scene(lat, lon, self._zoom))
        self.centerOn(new_center)
        self._load_visible_tiles()


class GeofenceWidget(QWidget):
    """Geofence tab with interactive map, controls for set/clear."""

    def __init__(self, actions: dict = None):
        super().__init__()
        self._actions = actions or {}
        self._marker_lat = 0.0
        self._marker_lon = 0.0
        self._car_lat = None
        self._car_lon = None
        self._geofence = None

        layout = QVBoxLayout(self)

        # Map
        self._map = _TileMapView(self)
        self._map.on_marker_moved = self._on_marker_moved
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

        self._refresh_btn = QPushButton(
            icon("refresh-cw"), t("geofence.refresh"))
        self._refresh_btn.clicked.connect(self._on_refresh)
        buttons.addWidget(self._refresh_btn)

        buttons.addStretch()
        layout.addLayout(buttons)

    def _on_marker_moved(self, lat, lon):
        self._marker_lat = lat
        self._marker_lon = lon
        self._coord_label.setText(f"{lat:.6f}, {lon:.6f}")

    def _call(self, name, *args):
        cb = self._actions.get(name)
        if cb:
            cb(*args)

    def _on_radius_changed(self, value):
        self._map.set_radius(value)

    def _on_use_car(self):
        if self._car_lat is not None and self._car_lon is not None:
            self._marker_lat = self._car_lat
            self._marker_lon = self._car_lon
            self._coord_label.setText(
                f"{self._car_lat:.6f}, {self._car_lon:.6f}")
            radius = self._radius_spin.value()
            self._map.set_marker(self._car_lat, self._car_lon, radius)

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
            self._status_label.setStyleSheet(
                "color: gray; font-weight: bold;")
            self._map.clear_marker()
            self._coord_label.setText("")
            return
        self._name_input.setText(geofence.name or "Geofence")
        self._radius_spin.setValue(int(geofence.radius or 1))
        self._marker_lat = geofence.latitude
        self._marker_lon = geofence.longitude
        self._coord_label.setText(
            f"{geofence.latitude:.6f}, {geofence.longitude:.6f}")
        if geofence.processing or geofence.waiting_activate:
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
        self._map.set_marker(geofence.latitude, geofence.longitude, radius)
