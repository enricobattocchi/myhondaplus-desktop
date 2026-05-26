"""Tests for the login widget."""

from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication, QLineEdit

from myhondaplus_desktop.widgets.login import LoginWidget

APP = QApplication.instance() or QApplication([])


def _make_widget():
    return LoginWidget(on_login_success=lambda *a, **k: None, storage=MagicMock())


def test_password_starts_masked():
    w = _make_widget()
    assert w._password.echoMode() == QLineEdit.EchoMode.Password


def test_password_toggle_reveals_then_hides():
    w = _make_widget()
    w._toggle_password_visibility()
    assert w._password.echoMode() == QLineEdit.EchoMode.Normal
    w._toggle_password_visibility()
    assert w._password.echoMode() == QLineEdit.EchoMode.Password
