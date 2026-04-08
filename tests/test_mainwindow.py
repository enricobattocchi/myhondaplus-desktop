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


class DummyTokens:
    def __init__(self):
        self.access_token = ""
        self.refresh_token = ""
        self.is_expired = False


class DummyAPI:
    def __init__(self, storage):
        self.storage = storage
        self.tokens = DummyTokens()
        self.set_tokens_calls = []
        self.refresh_auth_calls = 0

    def set_tokens(self, **kwargs):
        self.set_tokens_calls.append(kwargs)

    def refresh_auth(self):
        self.refresh_auth_calls += 1


def _patch_window_dependencies(monkeypatch, tmp_path, storage, api_factory):
    monkeypatch.setattr("myhondaplus_desktop.app.Settings.load", classmethod(lambda cls: Settings()))
    monkeypatch.setattr("myhondaplus_desktop.app.token_file", lambda: tmp_path / "data" / "tokens.json")
    monkeypatch.setattr("myhondaplus_desktop.app.device_key_file", lambda: tmp_path / "data" / "device.pem")
    monkeypatch.setattr("myhondaplus_desktop.app.get_storage", lambda *_: storage)
    monkeypatch.setattr("myhondaplus_desktop.app.HondaAPI", api_factory)
    monkeypatch.setattr("myhondaplus_desktop.app.LoginWidget", DummyLoginWidget)
    monkeypatch.setattr("myhondaplus_desktop.app.MainScreen", DummyMainScreen)


def test_mainwindow_uses_app_storage_paths(monkeypatch, tmp_path):
    storage = DummyStorage()
    api_instances = []
    calls = {}

    def fake_get_storage(token_path, device_key_path):
        calls["token_path"] = token_path
        calls["device_key_path"] = device_key_path
        return storage

    def fake_honda_api(*, storage):
        api = DummyAPI(storage)
        api_instances.append(api)
        return api

    monkeypatch.setattr("myhondaplus_desktop.app.token_file", lambda: tmp_path / "data" / "tokens.json")
    monkeypatch.setattr("myhondaplus_desktop.app.device_key_file", lambda: tmp_path / "data" / "device.pem")
    monkeypatch.setattr("myhondaplus_desktop.app.get_storage", fake_get_storage)
    monkeypatch.setattr("myhondaplus_desktop.app.HondaAPI", fake_honda_api)
    monkeypatch.setattr("myhondaplus_desktop.app.LoginWidget", DummyLoginWidget)
    monkeypatch.setattr("myhondaplus_desktop.app.MainScreen", DummyMainScreen)

    window = MainWindow()

    assert calls["token_path"] == tmp_path / "data" / "tokens.json"
    assert calls["device_key_path"] == tmp_path / "data" / "device.pem"
    assert calls["token_path"].parent.exists()
    assert calls["device_key_path"].parent.exists()
    assert window._login.storage is storage
    assert window._main._api is api_instances[0]


def test_mainwindow_login_success_updates_api_and_activates_main(monkeypatch, tmp_path):
    storage = DummyStorage()

    _patch_window_dependencies(
        monkeypatch,
        tmp_path,
        storage,
        lambda *, storage: DummyAPI(storage),
    )
    monkeypatch.setattr("myhondaplus_desktop.app.HondaAuth.extract_user_id", lambda token: "user-123")

    window = MainWindow()
    tokens = {"access_token": "access", "refresh_token": "refresh", "expires_in": 7200}

    window._on_login_success(tokens, "user@example.com", "secret")

    assert window._api.set_tokens_calls == [{
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_in": 7200,
        "user_id": "user-123",
    }]
    assert window._stack.currentWidget() is window._main
    assert window._main.activated == 1


def test_mainwindow_logout_clears_storage_and_replaces_api(monkeypatch, tmp_path):
    storage = DummyStorage()
    api_instances = []

    def fake_honda_api(*, storage):
        api = DummyAPI(storage)
        api_instances.append(api)
        return api

    _patch_window_dependencies(monkeypatch, tmp_path, storage, fake_honda_api)

    window = MainWindow()
    first_api = window._api

    window._logout()

    assert storage.clear_calls == 1
    assert len(api_instances) == 2
    assert first_api is not window._api
    assert window._main._api is window._api
    assert window._stack.currentWidget() is window._login
