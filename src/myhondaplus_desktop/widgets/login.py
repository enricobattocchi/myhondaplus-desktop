"""Login screen widget."""

from pymyhondaplus import SecretStorage
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFormLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import t
from ..workers import (
    DeviceRegistrationWorker,
    LoginWorker,
    VerifyAndLoginWorker,
)


class LoginWidget(QWidget):
    def __init__(self, on_login_success, storage: SecretStorage):
        super().__init__()
        self._on_login_success = on_login_success
        self._storage = storage
        self._worker = None
        self._reg_worker = None
        self._verify_worker = None
        self._auth = None

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        from ..icons import pixmap
        icon_lbl = QLabel()
        icon_lbl.setPixmap(pixmap("app-icon", 96))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_lbl)

        title = QLabel(t("app.name"))
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 20px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Fixed-width container for form
        form_container = QWidget()
        form_container.setFixedWidth(350)
        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(0, 0, 0, 0)

        form = QFormLayout()
        self._email = QLineEdit()
        self._email.setPlaceholderText(t("login.email_placeholder"))
        form.addRow(t("login.email"), self._email)

        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText(t("login.password_placeholder"))
        form.addRow(t("login.password"), self._password)

        form_layout.addLayout(form)

        self._login_btn = QPushButton(t("login.button"))
        self._login_btn.setMinimumHeight(36)
        self._login_btn.clicked.connect(self._do_login)
        form_layout.addWidget(self._login_btn)

        help_text = QLabel(t("login.help_text"))
        help_text.setStyleSheet("color: gray; font-size: 11px; margin-top: 4px;")
        help_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        help_text.setWordWrap(True)
        form_layout.addWidget(help_text)

        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setWordWrap(True)
        form_layout.addWidget(self._status)

        layout.addWidget(form_container, alignment=Qt.AlignmentFlag.AlignCenter)

        from .. import __version__
        version_lbl = QLabel(f"v{__version__}")
        version_lbl.setStyleSheet("color: gray; font-size: 11px; margin-top: 10px;")
        version_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_lbl)

        self._password.returnPressed.connect(self._do_login)

    def _do_login(self):
        email = self._email.text().strip()
        password = self._password.text()
        if not email or not password:
            self._status.setText(t("login.enter_credentials"))
            return

        self._login_btn.setEnabled(False)
        self._status.setText(t("login.logging_in"))

        self._worker = LoginWorker(email, password, storage=self._storage)
        self._worker.finished.connect(self._on_login_done)
        self._worker.error.connect(self._on_login_error)
        self._worker.progress.connect(self._status.setText)
        self._worker.device_registration_needed.connect(
            self._on_device_registration_needed)
        self._worker.start()

    def _on_login_done(self, tokens):
        self._status.setText(t("login.success"))
        self._login_btn.setEnabled(True)
        self._on_login_success(
            tokens, self._email.text().strip(), self._password.text())

    def _on_login_error(self, msg):
        self._status.setText(t("login.error", message=msg))
        self._login_btn.setEnabled(True)

    def _on_device_registration_needed(self):
        self._status.setText(t("login.device_not_registered"))

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
        self._status.setText(t("login.check_email"))
        link, ok = QInputDialog.getText(
            self, t("login.verification_title"),
            t("login.verification_text"),
        )
        if not ok or not link.strip():
            self._status.setText(t("login.verification_cancelled"))
            self._login_btn.setEnabled(True)
            return

        self._verify_worker = VerifyAndLoginWorker(
            auth, email, password, link.strip())
        self._verify_worker.finished.connect(self._on_login_done)
        self._verify_worker.error.connect(self._on_login_error)
        self._verify_worker.progress.connect(self._status.setText)
        self._verify_worker.start()
