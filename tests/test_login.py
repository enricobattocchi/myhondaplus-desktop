"""Tests for the login widget."""

from unittest.mock import MagicMock

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QLineEdit

from myhondaplus_desktop.widgets.login import LoginWidget

APP = QApplication.instance() or QApplication([])


def _make_widget(email=""):
    return LoginWidget(
        on_login_success=lambda *a, **k: None, storage=MagicMock(), email=email)


def test_password_starts_masked():
    w = _make_widget()
    assert w._password.echoMode() == QLineEdit.EchoMode.Password


def test_password_toggle_reveals_then_hides():
    w = _make_widget()
    w._toggle_password_visibility()
    assert w._password.echoMode() == QLineEdit.EchoMode.Normal
    w._toggle_password_visibility()
    assert w._password.echoMode() == QLineEdit.EchoMode.Password


def test_email_starts_empty_without_remembered_email():
    w = _make_widget()
    assert w._email.text() == ""


def test_email_prefilled_with_remembered_email():
    w = _make_widget("user@example.com")
    assert w._email.text() == "user@example.com"


def test_focus_on_password_when_email_prefilled():
    w = _make_widget("user@example.com")
    w.show()
    APP.processEvents()
    assert w.focusWidget() is w._password
    w.hide()


def test_focus_on_email_without_remembered_email():
    w = _make_widget()
    w.show()
    APP.processEvents()
    assert w.focusWidget() is w._email
    w.hide()


def test_reset_keeps_email_and_clears_password():
    w = _make_widget()
    w._email.setText("user@example.com")
    w._password.setText("secret")
    w._status.setText("Logged in")
    w._set_inputs_enabled(False)

    w.reset("user@example.com")

    assert w._email.text() == "user@example.com"
    assert w._password.text() == ""
    assert w._status.text() == ""
    assert w._login_btn.isEnabled()
    assert w._email.isEnabled()
    assert w._password.isEnabled()


def test_fields_locked_while_login_runs(monkeypatch):
    started = []

    class FakeWorker(QObject):
        result_ready = pyqtSignal(dict)
        error = pyqtSignal(str)
        progress = pyqtSignal(str)
        device_registration_needed = pyqtSignal()

        def __init__(self, *args, **kwargs):
            super().__init__()

        def start(self):
            started.append(self)

    monkeypatch.setattr("myhondaplus_desktop.widgets.login.LoginWorker", FakeWorker)
    w = _make_widget("user@example.com")
    w._password.setText("secret")

    w._do_login()

    assert started
    assert not w._email.isEnabled()
    assert not w._password.isEnabled()
    assert not w._login_btn.isEnabled()

    w._on_login_error("boom")

    assert w._email.isEnabled()
    assert w._password.isEnabled()
    assert w._login_btn.isEnabled()
