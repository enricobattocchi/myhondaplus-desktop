"""Tests for main window bootstrap and session flow."""

from PyQt6.QtWidgets import QApplication, QWidget

from myhondaplus_desktop.app import MainWindow
from myhondaplus_desktop.config import Settings

APP = QApplication.instance() or QApplication([])
APP.setQuitOnLastWindowClosed(False)


class DummyLoginWidget(QWidget):
    def __init__(self, on_login_success, storage):
        super().__init__()
        self.on_login_success = on_login_success
        self.storage = storage


class DummyMainScreen(QWidget):
    def __init__(self, api, settings, on_logout):
        super().__init__()
        self._api = api
        self.settings = settings
        self.on_logout = on_logout
        self.activated = 0

    def activate(self):
        self.activated += 1


class DummyStorage:
    def __init__(self):
        self.clear_calls = 0

    def clear(self):
        self.clear_calls += 1


class DummyAPI:
    def __init__(self, name: str):
        self.name = name
        self.set_tokens_calls = []

    def set_tokens(self, **kwargs):
        self.set_tokens_calls.append(kwargs)


class DummySession:
    def __init__(self):
        self.settings = Settings()
        self.storage = DummyStorage()
        self.api = DummyAPI("initial")
        self.restore_result = False
        self.applied_tokens = []
        self.reset_calls = 0
        self.saved = 0

    def restore_authenticated_session(self):
        return self.restore_result

    def apply_login_tokens(self, tokens):
        self.applied_tokens.append(tokens)

    def reset(self):
        self.reset_calls += 1
        self.api = DummyAPI("reset")
        return self.api

    def save_settings(self):
        self.saved += 1


def _patch_window_dependencies(monkeypatch, session):
    monkeypatch.setattr("myhondaplus_desktop.app.AppSession", lambda: session)
    monkeypatch.setattr("myhondaplus_desktop.app.LoginWidget", DummyLoginWidget)
    monkeypatch.setattr("myhondaplus_desktop.app.MainScreen", DummyMainScreen)


def test_mainwindow_uses_session_storage_and_api(monkeypatch):
    session = DummySession()
    _patch_window_dependencies(monkeypatch, session)

    window = MainWindow()

    assert window._login.storage is session.storage
    assert window._main._api is session.api
    assert window._settings is session.settings


def test_mainwindow_shows_main_screen_when_session_restores(monkeypatch):
    session = DummySession()
    session.restore_result = True
    _patch_window_dependencies(monkeypatch, session)

    window = MainWindow()

    assert window._stack.currentWidget() is window._main
    assert window._main.activated == 1


def test_mainwindow_login_success_delegates_to_session(monkeypatch):
    session = DummySession()
    _patch_window_dependencies(monkeypatch, session)

    window = MainWindow()
    tokens = {"access_token": "access", "refresh_token": "refresh", "expires_in": 7200}

    window._on_login_success(tokens, "user@example.com", "secret")

    assert session.applied_tokens == [tokens]
    assert window._stack.currentWidget() is window._main
    assert window._main.activated == 1


def test_mainwindow_logout_resets_session_api(monkeypatch):
    session = DummySession()
    _patch_window_dependencies(monkeypatch, session)

    window = MainWindow()
    first_api = window._api

    window._logout()

    assert session.reset_calls == 1
    assert first_api is not window._api
    assert window._main._api is window._api
    assert window._stack.currentWidget() is window._login


def test_mainwindow_close_event_saves_session_settings(monkeypatch):
    session = DummySession()
    _patch_window_dependencies(monkeypatch, session)

    window = MainWindow()
    window.close()

    assert session.saved == 1
