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

from ..i18n import t
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
        h, val = _row("milestone", t("dashboard.odometer"))
        veh_layout.addLayout(h)
        self._odometer_label = val
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
        self._sub_box.setVisible(False)
        right = QVBoxLayout()
        right.addWidget(self._sub_box)
        right.addStretch()
        layout.addLayout(right)

    def set_vin(self, vin: str):
        self._vin_label.setText(vin)

    def set_vehicle_info(self, vehicle):
        self._model_label.setText(getattr(vehicle, "model_name", "") or "")
        self._grade_label.setText(getattr(vehicle, "grade", "") or "")
        self._year_label.setText(getattr(vehicle, "model_year", "") or "")

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
        self._sub_box.setVisible(True)

    def update_odometer(self, status):
        """Update odometer from dashboard status data."""
        odometer = status.get("odometer", "")
        dist = status.get("distance_unit", "km")
        if odometer:
            self._odometer_label.setText(f"{odometer:,} {dist}")
        else:
            self._odometer_label.setText("")
