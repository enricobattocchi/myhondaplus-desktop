"""Vehicle info and subscription widget (displayed as a tab)."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..i18n import active_capability_labels, t
from ..icons import pixmap


def _card(title: str, icon_name: str) -> tuple[QGroupBox, QVBoxLayout]:
    box = QGroupBox(title)
    box.setStyleSheet("QGroupBox { font-weight: bold; }")
    layout = QVBoxLayout(box)
    header = QHBoxLayout()
    icon_lbl = QLabel()
    icon_lbl.setPixmap(pixmap(icon_name, 20))
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
    header.addWidget(icon_lbl)
    header.addWidget(title_lbl)
    header.addStretch()
    box.setTitle("")
    layout.addLayout(header)
    return box, layout


def _selectable(label: QLabel) -> QLabel:
    label.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setCursor(Qt.CursorShape.IBeamCursor)
    return label


def _row(icon_name: str, label: str, value: str = "") -> tuple[QHBoxLayout, QLabel]:
    h = QHBoxLayout()
    icon_lbl = QLabel()
    icon_lbl.setPixmap(pixmap(icon_name, 14))
    icon_lbl.setFixedWidth(20)
    lbl = QLabel(label)
    lbl.setStyleSheet("color: gray;")
    val = _selectable(QLabel(value))
    h.addWidget(icon_lbl)
    h.addWidget(lbl)
    h.addStretch()
    h.addWidget(val)
    return h, val


class VehicleWidget(QWidget):
    """Shows static vehicle information and subscription details."""

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)

        # Vehicle card
        veh_box, veh_layout = _card(t("dashboard.vehicle"), "car")
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setVisible(False)
        veh_layout.addWidget(self._image_label)
        h, val = _row("clipboard", t("dashboard.vin"))
        veh_layout.addLayout(h)
        self._vin_label = val
        h, val = _row("car", t("dashboard.model"))
        veh_layout.addLayout(h)
        self._model_label = val
        h, val = _row("shield", t("dashboard.grade"))
        veh_layout.addLayout(h)
        self._grade_label = val
        h, val = _row("calendar", t("dashboard.year"))
        veh_layout.addLayout(h)
        self._year_label = val
        h, val = _row("fuel", t("dashboard.fuel"))
        veh_layout.addLayout(h)
        self._fuel_label = val
        h, val = _row("door-open", t("dashboard.doors"))
        veh_layout.addLayout(h)
        self._doors_label = val
        h, val = _row("settings", t("dashboard.transmission"))
        veh_layout.addLayout(h)
        self._transmission_label = val
        h, val = _row("gauge", t("dashboard.weight"))
        veh_layout.addLayout(h)
        self._weight_label = val
        h, val = _row("calendar", t("dashboard.registration"))
        veh_layout.addLayout(h)
        self._registration_label = val
        h, val = _row("calendar", t("dashboard.production"))
        veh_layout.addLayout(h)
        self._production_label = val
        h, val = _row("globe", t("dashboard.country"))
        veh_layout.addLayout(h)
        self._country_label = val
        h, val = _row("milestone", t("dashboard.odometer"))
        veh_layout.addLayout(h)
        self._odometer_label = val
        # Capabilities section
        cap_header = QHBoxLayout()
        cap_icon = QLabel()
        cap_icon.setPixmap(pixmap("settings", 14))
        cap_icon.setFixedWidth(20)
        self._cap_title = QLabel(t("dashboard.capabilities"))
        self._cap_title.setStyleSheet("color: gray; font-weight: bold;")
        cap_header.addWidget(cap_icon)
        cap_header.addWidget(self._cap_title)
        cap_header.addStretch()
        veh_layout.addLayout(cap_header)
        self._cap_container = QVBoxLayout()
        self._cap_container.setSpacing(2)
        self._cap_container.setContentsMargins(24, 0, 0, 0)
        veh_layout.addLayout(self._cap_container)
        self._cap_title.setVisible(False)
        left = QVBoxLayout()
        left.addWidget(veh_box)
        left.addStretch()
        layout.addLayout(left)

        # Subscription card
        self._sub_box, sub_layout = _card(t("dashboard.subscription"), "clipboard")
        sub_layout.setSpacing(4)
        h, val = _row("package", t("dashboard.package"))
        sub_layout.addLayout(h)
        self._sub_package_label = val
        h, val = _row("info", t("dashboard.sub_status"))
        sub_layout.addLayout(h)
        self._sub_status_label = val
        h, val = _row("fuel", t("dashboard.sub_price"))
        sub_layout.addLayout(h)
        self._sub_price_label = val
        h, val = _row("clock", t("dashboard.sub_payment"))
        sub_layout.addLayout(h)
        self._sub_payment_label = val
        h, val = _row("refresh-cw", t("dashboard.sub_renewal"))
        sub_layout.addLayout(h)
        self._sub_renewal_label = val
        h, val = _row("calendar", t("dashboard.sub_period"))
        sub_layout.addLayout(h)
        self._sub_period_label = val
        h, val = _row("calendar", t("dashboard.sub_next_payment"))
        sub_layout.addLayout(h)
        self._sub_next_payment_label = val
        # Services section
        svc_header = QHBoxLayout()
        svc_icon = QLabel()
        svc_icon.setPixmap(pixmap("settings", 14))
        svc_icon.setFixedWidth(20)
        self._sub_services_title = QLabel()
        self._sub_services_title.setStyleSheet("color: gray; font-weight: bold;")
        svc_header.addWidget(svc_icon)
        svc_header.addWidget(self._sub_services_title)
        svc_header.addStretch()
        sub_layout.addLayout(svc_header)
        self._sub_services_container = QVBoxLayout()
        self._sub_services_container.setSpacing(2)
        self._sub_services_container.setContentsMargins(24, 0, 0, 0)
        sub_layout.addLayout(self._sub_services_container)
        self._sub_services_title.setVisible(False)
        self._sub_box.setVisible(False)
        right = QVBoxLayout()
        right.addWidget(self._sub_box)
        right.addStretch()
        layout.addLayout(right)

    def set_vin(self, vin: str):
        self._vin_label.setText(vin)

    def set_capabilities(self, caps):
        while self._cap_container.count():
            item = self._cap_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if caps is None:
            self._cap_title.setVisible(False)
            return
        active_labels = active_capability_labels(caps)
        if active_labels:
            self._cap_title.setText(
                f"{t('dashboard.capabilities')} ({len(active_labels)})")
            for name in active_labels:
                lbl = QLabel(f"• {name}")
                lbl.setStyleSheet("font-size: 11px;")
                self._cap_container.addWidget(lbl)
        else:
            self._cap_title.setText(t("dashboard.capabilities"))
        self._cap_title.setVisible(True)

    def set_vehicle_info(self, vehicle):
        self._model_label.setText(getattr(vehicle, "model_name", "") or "")
        self._grade_label.setText(getattr(vehicle, "grade", "") or "")
        self._year_label.setText(getattr(vehicle, "model_year", "") or "")
        fuel = getattr(vehicle, "fuel_type", "") or ""
        if fuel:
            fuel_map = {"E": "ev", "X": "hybrid"}
            self._fuel_label.setText(self._tv(fuel_map.get(fuel, "petrol")))
        else:
            self._fuel_label.setText("")
        doors = getattr(vehicle, "doors", 0) or 0
        self._doors_label.setText(str(doors) if doors else "")
        trans = getattr(vehicle, "transmission", "") or ""
        if trans:
            trans_key = {"A": "automatic", "M": "manual"}.get(trans, trans)
            self._transmission_label.setText(self._tv(trans_key))
        else:
            self._transmission_label.setText("")
        weight = getattr(vehicle, "weight", 0) or 0
        self._weight_label.setText(f"{weight:.0f} kg" if weight else "")
        self._registration_label.setText(
            getattr(vehicle, "registration_date", "") or "")
        self._production_label.setText(
            getattr(vehicle, "production_date", "") or "")
        self._country_label.setText(
            getattr(vehicle, "country_code", "") or "")

    def set_vehicle_image(self, path: str):
        pm = QPixmap(path)
        if pm.isNull():
            self._image_label.setVisible(False)
            return
        self._image_label.setPixmap(
            pm.scaledToHeight(120, Qt.TransformationMode.SmoothTransformation))
        self._image_label.setVisible(True)

    @staticmethod
    def _tv(v: str) -> str:
        """Translate an API value string, fall back to raw value."""
        key = f"dashboard.val.{str(v).lower()}"
        result = t(key)
        return result if result != key else str(v)

    def set_subscription(self, subscription):
        if subscription is None:
            self._sub_box.setVisible(False)
            return
        self._sub_package_label.setText(getattr(subscription, "package_name", "") or "")
        status = getattr(subscription, "status", "") or ""
        self._sub_status_label.setText(self._tv(status) if status else "")
        price = getattr(subscription, "price", 0) or 0
        currency = getattr(subscription, "currency", "") or ""
        self._sub_price_label.setText(f"{price} {currency}" if price else "")
        payment = getattr(subscription, "payment_term", "") or ""
        self._sub_payment_label.setText(self._tv(payment) if payment else "")
        renewal = getattr(subscription, "renewal", False)
        self._sub_renewal_label.setText(t("dashboard.val.on") if renewal else t("dashboard.val.off"))
        start = getattr(subscription, "start_date", "") or ""
        end = getattr(subscription, "end_date", "") or ""
        period = f"{start} — {end}" if start and end else start or end
        self._sub_period_label.setText(period)
        self._sub_next_payment_label.setText(
            getattr(subscription, "next_payment_date", "") or "")
        # Services list
        while self._sub_services_container.count():
            item = self._sub_services_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        services = getattr(subscription, "services", []) or []
        if services:
            self._sub_services_title.setText(
                f"{t('dashboard.sub_services')} ({len(services)})")
            self._sub_services_title.setVisible(True)
            for svc in services:
                desc = getattr(svc, "description", "") or getattr(svc, "code", "")
                lbl = _selectable(QLabel(desc))
                lbl.setStyleSheet("font-size: 11px;")
                self._sub_services_container.addWidget(lbl)
        else:
            self._sub_services_title.setVisible(False)
        self._sub_box.setVisible(True)

    def update_odometer(self, status):
        """Update odometer from dashboard status data."""
        odometer = status.get("odometer", "")
        dist = status.get("distance_unit", "km")
        if odometer:
            self._odometer_label.setText(f"{odometer:,} {dist}")
        else:
            self._odometer_label.setText("")
