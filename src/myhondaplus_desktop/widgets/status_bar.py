"""Status bar widget for command feedback."""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer


class StatusBarWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)

        self._status = QLabel("Ready")
        layout.addWidget(self._status)

        layout.addStretch()

        self._timestamp = QLabel("")
        self._timestamp.setStyleSheet("color: gray;")
        layout.addWidget(self._timestamp)

    def set_status(self, text: str):
        self._status.setText(text)
        self._status.setStyleSheet("")

    def set_success(self, text: str):
        self._status.setText(text)
        self._status.setStyleSheet("color: green; font-weight: bold;")
        QTimer.singleShot(5000, lambda: self.set_status("Ready"))

    def set_error(self, text: str):
        self._status.setText(text)
        self._status.setStyleSheet("color: red;")

    def set_timestamp(self, text: str):
        self._timestamp.setText(text)
