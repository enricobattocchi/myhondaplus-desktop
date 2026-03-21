"""Login screen widget."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QInputDialog, QMessageBox,
)
from PyQt6.QtCore import Qt

from ..workers import (
    LoginWorker, DeviceRegistrationWorker, VerifyAndLoginWorker,
)
from pymyhondaplus.auth import DEFAULT_DEVICE_KEY_FILE, DeviceKey, HondaAuth


class LoginWidget(QWidget):
    def __init__(self, on_login_success):
        super().__init__()
        self._on_login_success = on_login_success
        self._worker = None
        self._reg_worker = None
        self._verify_worker = None
        self._auth = None

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("My Honda+")
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 20px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._email = QLineEdit()
        self._email.setPlaceholderText("user@example.com")
        self._email.setMinimumWidth(300)
        form.addRow("Email:", self._email)

        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("Password")
        form.addRow("Password:", self._password)

        layout.addLayout(form)

        self._login_btn = QPushButton("Login")
        self._login_btn.setMinimumHeight(36)
        self._login_btn.clicked.connect(self._do_login)
        layout.addWidget(self._login_btn)

        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._password.returnPressed.connect(self._do_login)

    def _do_login(self):
        email = self._email.text().strip()
        password = self._password.text()
        if not email or not password:
            self._status.setText("Enter email and password")
            return

        self._login_btn.setEnabled(False)
        self._status.setText("Logging in...")

        self._worker = LoginWorker(email, password)
        self._worker.finished.connect(self._on_login_done)
        self._worker.error.connect(self._on_login_error)
        self._worker.progress.connect(self._status.setText)
        self._worker.device_registration_needed.connect(
            self._on_device_registration_needed)
        self._worker.start()

    def _on_login_done(self, tokens):
        self._status.setText("Login successful!")
        self._login_btn.setEnabled(True)
        self._on_login_success(
            tokens, self._email.text().strip(), self._password.text())

    def _on_login_error(self, msg):
        self._status.setText(f"Error: {msg}")
        self._login_btn.setEnabled(True)

    def _on_device_registration_needed(self):
        self._status.setText("Device not registered. Requesting verification email...")

        auth = self._worker.auth
        email = self._email.text().strip()
        password = self._password.text()

        self._reg_worker = DeviceRegistrationWorker(auth, email, password)
        self._reg_worker.finished.connect(
            lambda: self._ask_for_verification_link(auth, email, password))
        self._reg_worker.error.connect(self._on_login_error)
        self._reg_worker.progress.connect(self._status.setText)
        self._reg_worker.start()

    def _ask_for_verification_link(self, auth, email, password):
        self._status.setText("Check your email!")
        link, ok = QInputDialog.getText(
            self, "Email Verification",
            "Check your email from Honda.\n"
            "DO NOT click the link — copy the URL and paste it here:",
        )
        if not ok or not link.strip():
            self._status.setText("Verification cancelled")
            self._login_btn.setEnabled(True)
            return

        self._verify_worker = VerifyAndLoginWorker(
            auth, email, password, link.strip())
        self._verify_worker.finished.connect(self._on_login_done)
        self._verify_worker.error.connect(self._on_login_error)
        self._verify_worker.progress.connect(self._status.setText)
        self._verify_worker.start()
