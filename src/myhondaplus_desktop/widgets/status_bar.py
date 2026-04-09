"""Status bar widget for command feedback."""

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ..i18n import t


class StatusBarWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)

        self._status = QLabel(t("status.ready"))
        layout.addWidget(self._status)

        layout.addStretch()

        self._timestamp = QLabel("")
        self._timestamp.setStyleSheet("color: gray;")
        layout.addWidget(self._timestamp)

        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.timeout.connect(lambda: self.set_status(t("status.ready")))

    def set_status(self, text: str):
        self._reset_timer.stop()
        self._status.setText(text)
        self._status.setStyleSheet("")

    def set_success(self, text: str):
        self._reset_timer.stop()
        self._status.setText(text)
        self._status.setStyleSheet("color: green; font-weight: bold;")
        self._reset_timer.start(5000)

    def set_warning(self, text: str):
        self._reset_timer.stop()
        self._status.setText(text)
        self._status.setStyleSheet("color: orange;")

    def set_error(self, text: str):
        self._reset_timer.stop()
        self._status.setText(text)
        self._status.setStyleSheet("color: red;")

    def set_timestamp(self, text: str):
        self._timestamp.setText(text)
