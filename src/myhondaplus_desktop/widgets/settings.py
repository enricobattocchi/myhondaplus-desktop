"""Settings tab embedded in the main window's QTabWidget.

Two-column layout: General + Tray on the left, Polling + Notifications on
the right. Each section is a ``QGroupBox`` so the visual grouping is
obvious without resorting to bold headings or manual separators. The
widget is wired live: every control writes straight back to the same
``Settings`` instance the rest of the app reads. Settings that need a
restart to take effect flip ``restart_required`` visible.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSpinBox,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from ..config import (
    ALLOWED_CACHED_INTERVALS,
    ALLOWED_CAR_REFRESH_HOURS,
    Settings,
)
from ..i18n import active_language, available_languages, t


def _hint_label(text: str) -> QLabel:
    """A small grey wrap-friendly note used under groups."""
    lbl = QLabel(text)
    lbl.setStyleSheet("color: gray; font-size: 11px;")
    lbl.setWordWrap(True)
    return lbl


class SettingsWidget(QWidget):
    """Embeddable settings panel. Lives as a tab in MainScreen."""

    def __init__(self, settings: Settings, parent: QWidget | None = None):
        super().__init__(parent)
        self._settings = settings

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        columns = QHBoxLayout()
        columns.setSpacing(16)
        columns.setContentsMargins(0, 0, 0, 0)
        root.addLayout(columns, 1)

        left = QVBoxLayout()
        left.setSpacing(12)
        right = QVBoxLayout()
        right.setSpacing(12)
        columns.addLayout(left, 1)
        columns.addLayout(right, 1)

        left.addWidget(self._build_general_group())
        left.addWidget(self._build_tray_group())
        left.addStretch(1)

        right.addWidget(self._build_polling_group())
        right.addWidget(self._build_notifications_group())
        right.addStretch(1)

        self._restart_label = QLabel(t("app.restart_required"))
        self._restart_label.setStyleSheet("color: gray; font-size: 11px;")
        self._restart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._restart_label.setVisible(False)
        root.addWidget(self._restart_label)

    # -- group builders -----------------------------------------------------

    def _build_general_group(self) -> QGroupBox:
        group = QGroupBox(t("settings.section.general"))
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        lang_combo = QComboBox()
        for code in available_languages():
            lang_combo.addItem(code, code)
        idx = lang_combo.findData(active_language())
        if idx >= 0:
            lang_combo.setCurrentIndex(idx)
        lang_combo.currentIndexChanged.connect(
            lambda _: self._on_language_changed(lang_combo.currentData()))
        form.addRow(t("app.language"), lang_combo)

        theme_combo = QComboBox()
        for value, label_key in (
            ("system", "app.theme_system"),
            ("light", "app.theme_light"),
            ("dark", "app.theme_dark"),
        ):
            theme_combo.addItem(t(label_key), value)
        idx = theme_combo.findData(self._settings.theme or "system")
        if idx >= 0:
            theme_combo.setCurrentIndex(idx)
        theme_combo.currentIndexChanged.connect(
            lambda _: self._on_theme_changed(theme_combo.currentData()))
        form.addRow(t("app.theme"), theme_combo)

        return group

    def _build_tray_group(self) -> QGroupBox:
        group = QGroupBox(t("settings.tray.heading"))
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        self._tray_enabled_cb = QCheckBox(t("settings.tray.enable"))
        self._tray_enabled_cb.setChecked(self._settings.tray_enabled)
        self._tray_enabled_cb.toggled.connect(self._on_tray_enabled_toggled)
        layout.addWidget(self._tray_enabled_cb)

        self._close_to_tray_cb = QCheckBox(t("settings.tray.close_to_tray"))
        self._close_to_tray_cb.setChecked(self._settings.close_to_tray)
        self._close_to_tray_cb.toggled.connect(self._on_close_to_tray_toggled)
        layout.addWidget(self._close_to_tray_cb)

        self._start_minimized_cb = QCheckBox(
            t("settings.tray.start_minimized"))
        self._start_minimized_cb.setChecked(self._settings.start_minimized)
        self._start_minimized_cb.toggled.connect(
            self._on_start_minimized_toggled)
        layout.addWidget(self._start_minimized_cb)

        if not QSystemTrayIcon.isSystemTrayAvailable():
            layout.addWidget(_hint_label(t("settings.tray.unavailable_hint")))

        return group

    def _build_polling_group(self) -> QGroupBox:
        group = QGroupBox(t("settings.polling.heading"))
        outer = QVBoxLayout(group)
        outer.setSpacing(6)

        self._poll_enabled_cb = QCheckBox(t("settings.polling.enable"))
        self._poll_enabled_cb.setChecked(self._settings.background_poll_enabled)
        self._poll_enabled_cb.toggled.connect(self._on_poll_enabled_toggled)
        outer.addWidget(self._poll_enabled_cb)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setContentsMargins(20, 0, 0, 0)  # indent under the checkbox

        self._poll_interval_combo = QComboBox()
        for minutes in ALLOWED_CACHED_INTERVALS:
            self._poll_interval_combo.addItem(
                t("settings.polling.minutes", minutes=minutes), minutes)
        idx = self._poll_interval_combo.findData(
            self._settings.background_poll_cached_interval_min)
        if idx >= 0:
            self._poll_interval_combo.setCurrentIndex(idx)
        self._poll_interval_combo.currentIndexChanged.connect(
            lambda _: self._on_poll_interval_changed(
                self._poll_interval_combo.currentData()))
        form.addRow(t("settings.polling.interval"), self._poll_interval_combo)
        outer.addLayout(form)

        self._car_refresh_enabled_cb = QCheckBox(
            t("settings.polling.car_refresh_enable"))
        self._car_refresh_enabled_cb.setChecked(
            self._settings.background_car_refresh_enabled)
        self._car_refresh_enabled_cb.toggled.connect(
            self._on_car_refresh_enabled_toggled)
        outer.addWidget(self._car_refresh_enabled_cb)

        car_form = QFormLayout()
        car_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        car_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        car_form.setContentsMargins(20, 0, 0, 0)

        self._car_refresh_combo = QComboBox()
        for hours in ALLOWED_CAR_REFRESH_HOURS:
            self._car_refresh_combo.addItem(
                t("settings.polling.hours", hours=hours), hours)
        idx = self._car_refresh_combo.findData(
            self._settings.background_car_refresh_hours)
        if idx >= 0:
            self._car_refresh_combo.setCurrentIndex(idx)
        self._car_refresh_combo.currentIndexChanged.connect(
            lambda _: self._on_car_refresh_interval_changed(
                self._car_refresh_combo.currentData()))
        car_form.addRow(
            t("settings.polling.car_refresh_interval"), self._car_refresh_combo)
        outer.addLayout(car_form)

        outer.addWidget(_hint_label(t("settings.polling.warning")))
        return group

    def _build_notifications_group(self) -> QGroupBox:
        group = QGroupBox(t("settings.notifications.heading"))
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        self._notify_charge_started_cb = QCheckBox(
            t("settings.notifications.charge_started"))
        self._notify_charge_started_cb.setChecked(
            self._settings.notify_charge_started)
        self._notify_charge_started_cb.toggled.connect(
            self._on_notify_charge_started_toggled)
        layout.addWidget(self._notify_charge_started_cb)

        self._notify_charge_stopped_cb = QCheckBox(
            t("settings.notifications.charge_stopped"))
        self._notify_charge_stopped_cb.setChecked(
            self._settings.notify_charge_stopped)
        self._notify_charge_stopped_cb.toggled.connect(
            self._on_notify_charge_stopped_toggled)
        layout.addWidget(self._notify_charge_stopped_cb)

        self._notify_climate_started_cb = QCheckBox(
            t("settings.notifications.climate_started"))
        self._notify_climate_started_cb.setChecked(
            self._settings.notify_climate_started)
        self._notify_climate_started_cb.toggled.connect(
            self._on_notify_climate_started_toggled)
        layout.addWidget(self._notify_climate_started_cb)

        self._notify_climate_stopped_cb = QCheckBox(
            t("settings.notifications.climate_stopped"))
        self._notify_climate_stopped_cb.setChecked(
            self._settings.notify_climate_stopped)
        self._notify_climate_stopped_cb.toggled.connect(
            self._on_notify_climate_stopped_toggled)
        layout.addWidget(self._notify_climate_stopped_cb)

        self._notify_door_cb = QCheckBox(
            t("settings.notifications.door_unlocked"))
        self._notify_door_cb.setChecked(self._settings.notify_door_unlocked)
        self._notify_door_cb.toggled.connect(self._on_notify_door_toggled)
        layout.addWidget(self._notify_door_cb)

        self._notify_warning_cb = QCheckBox(
            t("settings.notifications.warning_lit"))
        self._notify_warning_cb.setChecked(self._settings.notify_warning_lit)
        self._notify_warning_cb.toggled.connect(self._on_notify_warning_toggled)
        layout.addWidget(self._notify_warning_cb)

        battery_row = QHBoxLayout()
        battery_label = QLabel(t("settings.notifications.battery_low"))
        battery_row.addWidget(battery_label)
        self._notify_battery_spin = QSpinBox()
        self._notify_battery_spin.setRange(0, 100)
        self._notify_battery_spin.setSingleStep(5)
        self._notify_battery_spin.setSuffix(" %")
        self._notify_battery_spin.setSpecialValueText(
            t("settings.notifications.battery_low_disabled"))
        self._notify_battery_spin.setValue(self._settings.notify_battery_low_pct)
        self._notify_battery_spin.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._notify_battery_spin.valueChanged.connect(
            self._on_notify_battery_changed)
        battery_row.addWidget(self._notify_battery_spin)
        battery_row.addStretch(1)
        layout.addLayout(battery_row)

        layout.addWidget(_hint_label(t("settings.notifications.note")))
        return group

    # -- change handlers ----------------------------------------------------

    def _on_language_changed(self, lang_code: str):
        self._settings.language = lang_code
        self._settings.save()
        self._restart_label.setVisible(True)

    def _on_theme_changed(self, theme: str):
        self._settings.theme = theme
        self._settings.save()
        self._restart_label.setVisible(True)

    def _on_tray_enabled_toggled(self, checked: bool):
        self._settings.tray_enabled = checked
        self._settings.save()
        self._restart_label.setVisible(True)

    def _on_close_to_tray_toggled(self, checked: bool):
        self._settings.close_to_tray = checked
        self._settings.save()
        # closeEvent reads the live value; no restart needed.

    def _on_start_minimized_toggled(self, checked: bool):
        self._settings.start_minimized = checked
        self._settings.save()
        self._restart_label.setVisible(True)

    def _on_poll_enabled_toggled(self, checked: bool):
        self._settings.background_poll_enabled = checked
        self._settings.save()
        self._restart_label.setVisible(True)

    def _on_poll_interval_changed(self, minutes):
        if minutes is None:
            return
        self._settings.background_poll_cached_interval_min = int(minutes)
        self._settings.save()
        self._restart_label.setVisible(True)

    def _on_car_refresh_enabled_toggled(self, checked: bool):
        self._settings.background_car_refresh_enabled = checked
        self._settings.save()
        self._restart_label.setVisible(True)

    def _on_car_refresh_interval_changed(self, hours):
        if hours is None:
            return
        self._settings.background_car_refresh_hours = int(hours)
        self._settings.save()
        self._restart_label.setVisible(True)

    def _on_notify_charge_started_toggled(self, checked: bool):
        self._settings.notify_charge_started = checked
        self._settings.save()

    def _on_notify_charge_stopped_toggled(self, checked: bool):
        self._settings.notify_charge_stopped = checked
        self._settings.save()

    def _on_notify_climate_started_toggled(self, checked: bool):
        self._settings.notify_climate_started = checked
        self._settings.save()

    def _on_notify_climate_stopped_toggled(self, checked: bool):
        self._settings.notify_climate_stopped = checked
        self._settings.save()

    def _on_notify_door_toggled(self, checked: bool):
        self._settings.notify_door_unlocked = checked
        self._settings.save()

    def _on_notify_battery_changed(self, value: int):
        self._settings.notify_battery_low_pct = int(value)
        self._settings.save()

    def _on_notify_warning_toggled(self, checked: bool):
        self._settings.notify_warning_lit = checked
        self._settings.save()
